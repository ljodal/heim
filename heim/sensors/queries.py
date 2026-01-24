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
    Excludes measurements in any exclusion ranges.
    """
    since = datetime.now() - timedelta(hours=hours)
    rows = await db.fetch(
        """
        SELECT measured_at, value
        FROM sensor_measurement m
        WHERE m.sensor_id = $1
          AND m.attribute = $2
          AND m.measured_at > $3
          AND NOT EXISTS (
              SELECT 1 FROM sensor_measurement_exclusion e
              WHERE e.sensor_id = m.sensor_id
                AND e.excluded @> m.measured_at
          )
        ORDER BY m.measured_at ASC
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


async def add_exclusion(
    *, account_id: int, sensor_id: int, from_time: datetime, until_time: datetime
) -> int | None:
    """Add an exclusion range for a sensor. Returns exclusion id or None."""
    exclusion_id: int | None = await db.fetchval(
        """
        INSERT INTO sensor_measurement_exclusion (sensor_id, excluded)
        SELECT $1, tstzrange($2, $3, '[)')
        FROM sensor
        WHERE id = $1 AND account_id = $4
        RETURNING id
        """,
        sensor_id,
        from_time,
        until_time,
        account_id,
    )
    return exclusion_id


async def list_exclusions(
    *, account_id: int, sensor_id: int
) -> list[tuple[int, datetime, datetime]]:
    """List exclusion ranges for a sensor. Returns list of (id, from, until) tuples."""
    rows = await db.fetch(
        """
        SELECT e.id, lower(e.excluded) as from_time, upper(e.excluded) as until_time
        FROM sensor_measurement_exclusion e
        JOIN sensor s ON s.id = e.sensor_id
        WHERE e.sensor_id = $1 AND s.account_id = $2
        ORDER BY lower(e.excluded)
        """,
        sensor_id,
        account_id,
    )
    return [(row["id"], row["from_time"], row["until_time"]) for row in rows]


async def remove_exclusion(*, account_id: int, exclusion_id: int) -> bool:
    """Remove an exclusion range. Returns True if deleted."""
    result = await db.execute(
        """
        DELETE FROM sensor_measurement_exclusion e
        USING sensor s
        WHERE e.id = $1 AND e.sensor_id = s.id AND s.account_id = $2
        """,
        exclusion_id,
        account_id,
    )
    return result == "DELETE 1"
