from datetime import datetime

from .. import db
from ..sensors.types import Attribute


async def create_forecast(*, name: str, account_id: int, location_id: int) -> int:
    """
    Create a new forecast.
    """

    return await db.fetchval(
        """
        INSERT INTO forecast (account_id, location_id, name)
        VALUES ($1, $2, $3) RETURNING id
        """,
        account_id,
        location_id,
        name,
    )


@db.transaction()
async def create_forecast_instance(
    *,
    forecast_id: int,
    forecast_time: datetime,
    values: list[tuple[Attribute, datetime, int]],
) -> None:
    """
    Insert a forecast instance.
    """

    forecast_instance_id: int = await db.fetchval(
        """
        INSERT INTO forecast_instance (forecast_id, created_at)
        VALUES ($1, $2)
        ON CONFLICT (forecast_id, created_at) DO NOTHING
        RETURNING id
        """,
        forecast_id,
        forecast_time,
    )

    # If the forecast instance already existed the query above returns None.
    # We do not want to update an existing forecast instance, so we return
    # early.
    if forecast_instance_id is None:
        return

    await db.executemany(
        """
        INSERT INTO forecast_value (
            forecast_instance_id, attribute, measured_at, value
        ) VALUES ($1, $2, $3, $4)
        ON CONFLICT (forecast_instance_id, attribute, measured_at) DO NOTHING
        """,
        [
            (forecast_instance_id, attribute, timestamp, value)
            for attribute, timestamp, value in values
        ],
    )
