from collections.abc import Iterable
from datetime import datetime, timedelta

from .. import db
from .types import Attribute


async def get_sensors(
    *, account_id: int, location_id: int, is_outdoor: bool | None = None
) -> list[tuple[int, str | None, str | None]]:
    """
    Get sensors for a location. Returns list of (id, name, color) tuples.

    Args:
        is_outdoor: If True, only outdoor sensors. If False, only indoor.
                    If None, all sensors.
    """
    if is_outdoor is None:
        query = """
            SELECT id, name, color
            FROM sensor
            WHERE location_id = $1 AND account_id = $2
        """
        rows = await db.fetch(query, location_id, account_id)
    else:
        query = """
            SELECT id, name, color
            FROM sensor
            WHERE location_id = $1 AND account_id = $2
              AND COALESCE(is_outdoor, false) = $3
        """
        rows = await db.fetch(query, location_id, account_id, is_outdoor)
    return [(row["id"], row["name"], row["color"]) for row in rows]


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


async def get_measurements_averaged(
    *,
    sensor_id: int,
    attribute: Attribute,
    hours: int = 24,
    bucket_minutes: int = 60,
) -> list[tuple[datetime, float]]:
    """
    Get measurements for a sensor within the last N hours, averaged over time buckets.
    Returns list of (bucket_start, avg_value) tuples.
    Excludes measurements in any exclusion ranges.

    Args:
        sensor_id: The sensor to fetch measurements for.
        attribute: The measurement attribute (e.g., temperature).
        hours: Number of hours to look back.
        bucket_minutes: Size of time buckets in minutes for averaging.
    """
    since = datetime.now() - timedelta(hours=hours)
    rows = await db.fetch(
        """
        SELECT
            to_timestamp(
                floor(extract(epoch from measured_at) / ($4 * 60)) * ($4 * 60)
            ) AS bucket,
            avg(value) AS avg_value
        FROM sensor_measurement m
        WHERE m.sensor_id = $1
          AND m.attribute = $2
          AND m.measured_at > $3
          AND NOT EXISTS (
              SELECT 1 FROM sensor_measurement_exclusion e
              WHERE e.sensor_id = m.sensor_id
                AND e.excluded @> m.measured_at
          )
        GROUP BY bucket
        ORDER BY bucket ASC
        """,
        sensor_id,
        attribute,
        since,
        bucket_minutes,
    )
    return [(row["bucket"], float(row["avg_value"])) for row in rows]


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


async def get_all_sensors(
    *, account_id: int
) -> list[tuple[int, str | None, str | None, bool, str | None, str | None]]:
    """
    Get all sensors for an account with their details.
    Returns list of (id, name, location_name, is_outdoor, source, color) tuples.
    Source is 'netatmo', 'aqara', or None for sensors without integration link.
    """
    rows = await db.fetch(
        """
        SELECT
            s.id,
            s.name,
            l.name as location_name,
            COALESCE(s.is_outdoor, false) as is_outdoor,
            CASE
                WHEN ns.sensor_id IS NOT NULL THEN 'netatmo'
                WHEN aq.sensor_id IS NOT NULL THEN 'aqara'
                ELSE NULL
            END as source,
            s.color
        FROM sensor s
        JOIN location l ON l.id = s.location_id
        LEFT JOIN netatmo_sensor ns ON ns.sensor_id = s.id
        LEFT JOIN aqara_sensor aq ON aq.sensor_id = s.id
        WHERE s.account_id = $1
        ORDER BY l.name, s.name
        """,
        account_id,
    )
    return [
        (
            row["id"],
            row["name"],
            row["location_name"],
            row["is_outdoor"],
            row["source"],
            row["color"],
        )
        for row in rows
    ]


async def get_sensor(
    *, account_id: int, sensor_id: int
) -> tuple[int, str | None, int, str | None, bool, str | None] | None:
    """
    Get a single sensor by ID.
    Returns (id, name, location_id, location_name, is_outdoor, color) or None.
    """
    row = await db.fetchrow(
        """
        SELECT
            s.id,
            s.name,
            s.location_id,
            l.name as location_name,
            COALESCE(s.is_outdoor, false) as is_outdoor,
            s.color
        FROM sensor s
        JOIN location l ON l.id = s.location_id
        WHERE s.id = $1 AND s.account_id = $2
        """,
        sensor_id,
        account_id,
    )
    if not row:
        return None
    return (
        row["id"],
        row["name"],
        row["location_id"],
        row["location_name"],
        row["is_outdoor"],
        row["color"],
    )


async def update_sensor(
    *, account_id: int, sensor_id: int, name: str, is_outdoor: bool, color: str | None
) -> bool:
    """Update sensor name, is_outdoor flag, and color. Returns True if sensor exists."""
    result = await db.execute(
        """
        UPDATE sensor
        SET name = $2, is_outdoor = $3, color = $4
        WHERE id = $1 AND account_id = $5
        """,
        sensor_id,
        name,
        is_outdoor,
        color or None,  # Convert empty string to None
        account_id,
    )
    return result == "UPDATE 1"
