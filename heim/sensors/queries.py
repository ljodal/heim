from collections.abc import Iterable
from datetime import datetime, timedelta

from .. import db
from .types import Attribute


async def get_sensors(*, location_id: int) -> list[tuple[int, str | None]]:
    """
    Get all sensors for a location. Returns list of (id, name) tuples.
    """
    rows = await db.fetch(
        """
        SELECT id, name
        FROM sensor
        WHERE location_id = $1
        """,
        location_id,
    )
    return [(row["id"], row["name"]) for row in rows]


async def get_measurements(
    *, sensor_id: int, attribute: Attribute, hours: int = 24
) -> list[tuple[datetime, float]]:
    """
    Get measurements for a sensor within the last N hours.
    Returns list of (measured_at, value) tuples.
    """
    since = datetime.now() - timedelta(hours=hours)
    rows = await db.fetch(
        """
        SELECT measured_at, value
        FROM sensor_measurement
        WHERE sensor_id = $1 AND attribute = $2 AND measured_at > $3
        ORDER BY measured_at ASC
        """,
        sensor_id,
        attribute,
        since,
    )
    return [(row["measured_at"], row["value"]) for row in rows]


async def save_measurements(
    *, sensor_id: int, values: Iterable[tuple[Attribute, datetime, float]]
) -> None:
    """
    Insert a forecast instance.
    """

    await db.executemany(
        """
        INSERT INTO sensor_measurement (sensor_id, attribute, measured_at, value)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (sensor_id, attribute, measured_at) DO NOTHING
        """,
        [
            (sensor_id, attribute, timestamp, value)
            for attribute, timestamp, value in values
        ],
    )
