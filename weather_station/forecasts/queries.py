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
    attributes: dict[Attribute, list[tuple[datetime, float]]]
) -> None:
    """
    Insert a forecast instance.
    """

    forecast_instance_id: int = await db.fetchval(
        """
        INSERT INTO forecast_instance (forecast_id, created_at)
        VALUES ($1, $2) RETURNING id
        """,
        forecast_id,
        forecast_time,
    )

    await db.executemany(
        """
        INSERT INTO forecast_value (
            forecast_instance_id, attribute, measured_at, value
        ) VALUES ($1, $2, $3, $4)
        """,
        [
            (forecast_instance_id, attribute, timestamp, value)
            for attribute, values in attributes.items()
            for timestamp, value in values
        ],
    )
