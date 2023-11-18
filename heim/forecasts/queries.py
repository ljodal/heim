from datetime import datetime

from .. import db
from ..sensors.types import Attribute


async def create_forecast(*, name: str, account_id: int, location_id: int) -> int:
    """
    Create a new forecast.
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
    return forecast_id


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


async def get_forecast_coordinate(*, forecast_id: int) -> tuple[float, float] | None:
    """
    Get the coordinate for the given forecast.
    """

    coordinate: tuple[float, float] | None = await db.fetchval(
        """
        SELECT l.coordinate
        FROM forecast f JOIN location l ON l.id = f.location_id
        WHERE f.id = $1
        """,
        forecast_id,
    )
    return coordinate


async def get_forecast(*, account_id: int, location_id: int) -> int | None:
    forecast_id: int | None = await db.fetchval(
        "SELECT id FROM forecast WHERE account_id = $1 AND location_id = $2 LIMIT 1",
        account_id,
        location_id,
    )
    return forecast_id


async def get_instances(
    *, forecast_id: int, attribute: Attribute
) -> dict[datetime, tuple[datetime, int]]:
    """
    Get three instances for the given forecast: latest, 12 hours old and 24 hours old.
    """

    # Figure out which instances we are interested in
    row = await db.fetchrow(
        """
        SELECT
            (
                SELECT id
                FROM forecast_instance
                WHERE forecast_id = $1
                ORDER BY created_at DESC LIMIT 1
            ),
            (
                SELECT id
                FROM forecast_instance
                WHERE forecast_id = $1 AND created_at < now() - '12 hours'::interval
                ORDER BY created_at DESC LIMIT 1
            ),
            (
                SELECT id
                FROM forecast_instance
                WHERE forecast_id = $1 AND created_at < now() - '24 hours'::interval
                ORDER BY created_at DESC LIMIT 1
            )
        """,
        forecast_id,
    )
    if not row:
        return {}

    latest, twelve_hours, one_day = row

    rows = await db.fetch(
        """
        SELECT created_at, array_agg((measured_at, value) ORDER BY measured_at) as values
        FROM forecast_instance i JOIN forecast_value v ON v.forecast_instance_id = i.id
        WHERE id IN ($1, $2, $3) AND attribute = $4
        GROUP BY id
        ORDER BY created_at DESC
        """,
        latest,
        twelve_hours,
        one_day,
        attribute,
    )

    return {created_at: values for created_at, values in rows}
