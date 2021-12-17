from datetime import datetime

from .. import db
from ..db.types import Attribute


@db.transaction()  # type: ignore
async def create_yr_forecast(
    *, account_id: int, name: str, coordinate: tuple[float, float], location_id: int
) -> int:
    """
    Create a forecast to be populated from YR.
    """

    forecast_id: int = await db.fetchval(
        """
        INSERT INTO forecast (account_id, location_id, name)
        VALUES ($1, $2, $3) RETURNING id
        """,
        account_id,
        location_id,
        name,
    )

    await db.execute(
        """
        INSERT INTO yr_forecast (account_id, forecast_id, name, coordinate)
        VALUES ($1, $2, $3, $4)
        """,
        account_id,
        forecast_id,
        name,
        coordinate,
    )

    return forecast_id


@db.transaction()  # type: ignore
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
