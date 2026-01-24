from collections.abc import Iterable
from datetime import datetime, timedelta

from .. import db
from .types import Attribute


async def get_sensors(
    *, account_id: int, location_id: int
) -> list[tuple[int, str | None]]:
    """
    Get all sensors for a location. Returns list of (id, name) tuples.
    """
    rows = await db.fetch(
        """
        SELECT id, name
        FROM sensor
        WHERE location_id = $1 AND account_id = $2
        """,
        location_id,
        account_id,
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


async def get_outdoor_sensors(
    *, account_id: int, location_id: int
) -> list[tuple[int, str | None]]:
    """Get all outdoor sensors for a location."""
    rows = await db.fetch(
        """
        SELECT id, name
        FROM sensor
        WHERE location_id = $1 AND account_id = $2 AND is_outdoor = true
        """,
        location_id,
        account_id,
    )
    return [(row["id"], row["name"]) for row in rows]


async def set_outdoor_sensor(
    *, account_id: int, sensor_id: int, is_outdoor: bool
) -> bool:
    """Set or clear the outdoor flag for a sensor. Returns True if sensor exists."""
    result = await db.execute(
        """
        UPDATE sensor
        SET is_outdoor = $2
        WHERE id = $1 AND account_id = $3
        """,
        sensor_id,
        is_outdoor,
        account_id,
    )
    return result == "UPDATE 1"
