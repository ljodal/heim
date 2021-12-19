import functools
import inspect
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, Concatenate, ParamSpec, TypeVar

import structlog

from ... import db
from ...sensors.queries import save_measurements
from ...sensors.types import Attribute
from .client import AqaraClient
from .exceptions import ExpiredAccessToken
from .queries import get_aqara_account, get_aqara_sensor, update_aqara_account

P = ParamSpec("P")
R = TypeVar("R")

logger = structlog.get_logger()


def with_aqara_client(
    func: Callable[Concatenate[AqaraClient, P], Awaitable[R]]  # type: ignore
) -> Callable[P, Awaitable[R]]:
    """
    A decorator that injects an aqara client to the decorated function. The
    decorated function must have an account_id keyword argument that will be
    used to look up the access token.

    This will also automatically refresh access tokens if it catches an
    ExpiredAccessToken exception and call the decorated function again with a
    new access token. Because of this decorated functions should be idempotent.
    """

    parameters = inspect.signature(func).parameters
    assert "account_id" in parameters

    @functools.wraps(func)
    async def inner(*args: P.args, **kwargs: P.kwargs) -> R:  # type: ignore
        account = await get_aqara_account(account_id=kwargs["account_id"])
        async with AqaraClient(access_token=account.access_token) as client:
            try:
                return await func(client, *args, **kwargs)
            except ExpiredAccessToken:
                logger.warning("Access token has expired, refreshing")
                # The access token has expired, so refresh it and retry
                await refresh_access_token(client, account_id=kwargs["account_id"])
                return await func(client, *args, **kwargs)

    return inner


async def refresh_access_token(client: AqaraClient, *, account_id: int) -> None:
    """
    Refresh the aqara access token for the given account.
    """

    async with db.connection() as con:
        if con.is_in_transaction():
            raise RuntimeError("Cannot refresh access token in a transaction")

        async with con.transaction():
            account = await get_aqara_account(account_id=account_id, for_update=True)

            response = await client.refresh_token(refresh_token=account.refresh_token)
            client.access_token = response.access_token

            await update_aqara_account(
                account,
                refresh_token=response.refresh_token,
                access_token=response.access_token,
                expires_at=(
                    datetime.now(timezone.utc) + timedelta(seconds=response.expires_in)
                ),
            )


MODEL_TO_RESOURCES = {
    "lumi.airmonitor.acn01": ("0.2.85", "0.1.85"),  # Air quality: 0.3.85
    "lumi.plug.maeu01": ("0.1.85", "0.2.85", "0.3.85"),
    "lumi.weather.v1": ("4.1.85", "0.13.85", "0.12.85"),
}

RESOURCE_TO_ATTRIBUTE = {
    "0.1.85": Attribute.AIR_TEMPERATURE,
    "0.2.85": Attribute.HUMIDITY,
    "0.3.85": Attribute.AIR_PRESSURE,
    "0.12.85": Attribute.POWER,
    "0.13.85": Attribute.ENERGY,
    "4.1.85": Attribute.POWER_STATE,
}


@with_aqara_client
async def update_sensor_data(
    client: AqaraClient, *, account_id: int, sensor_id: int
) -> None:
    """
    Load and save measurements for the given sensor data.
    """

    aqara_id, model, last_measurement = await get_aqara_sensor(
        account_id=account_id, sensor_id=sensor_id
    )

    # Accoring to the Aqara documentation historical data is available 7 days
    # back, so we default to loading as far back as we can if we have no
    # previous data for the sensor.
    if last_measurement is None:
        last_measurement = datetime.now(timezone.utc) - timedelta(days=7)

    resource_ids = MODEL_TO_RESOURCES[model]

    measurements = await client.get_resource_history(
        device_id=aqara_id, resource_ids=resource_ids, from_time=last_measurement
    )

    await save_measurements(
        sensor_id=sensor_id,
        values=(
            (
                RESOURCE_TO_ATTRIBUTE[measurement.resource_id],
                measurement.timestamp,
                measurement.value,
            )
            for measurement in measurements
        ),
    )
