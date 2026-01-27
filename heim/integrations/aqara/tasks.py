from datetime import UTC, datetime, timedelta

import structlog

from ...sensors.queries import save_measurements
from ...sensors.types import Attribute
from ...tasks import task
from ..common import random_delay
from .client import AqaraClient
from .queries import get_aqara_sensor
from .types import QueryResourceHistoryResult

logger = structlog.get_logger()

MODEL_TO_RESOURCE_MAPPING: dict[str, dict[str, Attribute]] = {
    "lumi.airmonitor.acn01": {
        "0.1.85": Attribute.AIR_TEMPERATURE,
        "0.2.85": Attribute.HUMIDITY,
        # "0.3.85": Attribute.AIR_QUALITY,
    },
    "lumi.plug.maeu01": {
        "0.12.85": Attribute.POWER,
        "0.13.85": Attribute.ENERGY,
        "4.1.85": Attribute.POWER_STATE,
    },
    "lumi.weather.v1": {
        "0.1.85": Attribute.AIR_TEMPERATURE,
        "0.2.85": Attribute.HUMIDITY,
        "0.3.85": Attribute.AIR_PRESSURE,
        "8.0.2008": Attribute.BATTERY_VOLTAGE,
        "8.0.9001": Attribute.BATTERY_LOW,
    },
    "lumi.sensor_ht.agl02": {
        "0.1.85": Attribute.AIR_TEMPERATURE,
        "0.2.85": Attribute.HUMIDITY,
        "0.3.85": Attribute.AIR_PRESSURE,
        "8.0.2008": Attribute.BATTERY_VOLTAGE,
        "8.0.9001": Attribute.BATTERY_LOW,
    },
}


@task(name="update-aqara-sensor-data", allow_skip=True, atomic=False)
@AqaraClient.authenticated()
async def update_sensor_data(
    client: AqaraClient,
    *,
    account_id: int,
    sensor_id: int,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
) -> None:
    """
    Load and save measurements for the given sensor.
    """

    aqara_id, model, last_update_time = await get_aqara_sensor(
        account_id=account_id, sensor_id=sensor_id
    )

    # Accoring to the Aqara documentation historical data is available 7 days
    # back, so we default to loading as far back as we can if we have no
    # previous data for the sensor.
    if from_time is None:
        from_time = last_update_time or datetime.now(UTC) - timedelta(days=7)

    resource_mapping = MODEL_TO_RESOURCE_MAPPING[model]

    logger.info(
        "Starting sensor data fetch",
        sensor_id=sensor_id,
        aqara_id=aqara_id,
        model=model,
        from_time=from_time.isoformat(),
    )

    # Loop and load measurements until we don't get any new data
    total_measurements = 0
    result: QueryResourceHistoryResult | None = None
    while True:
        result = await client.get_resource_history(
            device_id=aqara_id,
            resource_ids=resource_mapping,
            from_time=from_time,
            to_time=to_time,
            scan_id=result.scan_id if result else None,
        )
        if not result.data:
            break

        total_measurements += len(result.data)

        await save_measurements(
            sensor_id=sensor_id,
            values=(
                (
                    resource_mapping[measurement.resource_id],
                    measurement.timestamp,
                    measurement.value,
                )
                for measurement in result.data
            ),
        )

        # If no scan_id returned, we've reached the end of pagination
        if not result.scan_id:
            break

        logger.info(
            "Fetched measurements",
            sensor_id=sensor_id,
            batch_size=len(result.data),
            total=total_measurements,
        )

        # Add random delay between requests to avoid overwhelming the API
        await random_delay()

    logger.info(
        "Finished sensor data fetch",
        sensor_id=sensor_id,
        total_measurements=total_measurements,
    )
