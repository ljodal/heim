"""
Zone queries for managing logical measurement locations.

Zones represent places we want to track measurements over time (e.g., "Living Room").
Sensors are assigned to zones for specific time periods via sensor_zone_assignment.
"""

from datetime import datetime, timedelta

from .. import db
from ..sensors.types import Attribute


async def get_zones(
    *, account_id: int, location_id: int, is_outdoor: bool | None = None
) -> list[tuple[int, str, str | None]]:
    """
    Get zones for a location. Returns list of (id, name, color) tuples.

    Args:
        is_outdoor: If True, only outdoor zones. If False, only indoor.
                    If None, all zones.
    """
    if is_outdoor is None:
        query = """
            SELECT z.id, z.name, z.color
            FROM zone z
            JOIN location l ON l.id = z.location_id
            WHERE z.location_id = $1 AND l.account_id = $2
            ORDER BY z.name
        """
        rows = await db.fetch(query, location_id, account_id)
    else:
        query = """
            SELECT z.id, z.name, z.color
            FROM zone z
            JOIN location l ON l.id = z.location_id
            WHERE z.location_id = $1 AND l.account_id = $2 AND z.is_outdoor = $3
            ORDER BY z.name
        """
        rows = await db.fetch(query, location_id, account_id, is_outdoor)
    return [(row["id"], row["name"], row["color"]) for row in rows]


async def get_zone(
    *, account_id: int, zone_id: int
) -> tuple[int, str, int, str, bool, str | None] | None:
    """
    Get a single zone by ID.
    Returns (id, name, location_id, location_name, is_outdoor, color) or None.
    """
    row = await db.fetchrow(
        """
        SELECT
            z.id,
            z.name,
            z.location_id,
            l.name as location_name,
            z.is_outdoor,
            z.color
        FROM zone z
        JOIN location l ON l.id = z.location_id
        WHERE z.id = $1 AND l.account_id = $2
        """,
        zone_id,
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


async def get_all_zones(
    *, account_id: int
) -> list[tuple[int, str, str, bool, str | None, int | None]]:
    """
    Get all zones for an account with their details.

    Returns list of (id, name, location_name, is_outdoor, color, current_sensor_id).
    current_sensor_id is the currently assigned sensor (if any).
    """
    rows = await db.fetch(
        """
        SELECT
            z.id,
            z.name,
            l.name as location_name,
            z.is_outdoor,
            z.color,
            (
                SELECT sza.sensor_id
                FROM sensor_zone_assignment sza
                WHERE sza.zone_id = z.id
                  AND sza.active_range @> now()::timestamptz
                LIMIT 1
            ) as current_sensor_id
        FROM zone z
        JOIN location l ON l.id = z.location_id
        WHERE l.account_id = $1
        ORDER BY l.name, z.name
        """,
        account_id,
    )
    return [
        (
            row["id"],
            row["name"],
            row["location_name"],
            row["is_outdoor"],
            row["color"],
            row["current_sensor_id"],
        )
        for row in rows
    ]


async def create_zone(
    *,
    account_id: int,
    location_id: int,
    name: str,
    is_outdoor: bool = False,
    color: str | None = None,
) -> int | None:
    """
    Create a new zone.

    Returns the zone ID or None if location doesn't belong to account.
    """
    zone_id: int | None = await db.fetchval(
        """
        INSERT INTO zone (location_id, name, is_outdoor, color)
        SELECT $1, $2, $3, $4
        FROM location
        WHERE id = $1 AND account_id = $5
        RETURNING id
        """,
        location_id,
        name,
        is_outdoor,
        color,
        account_id,
    )
    return zone_id


async def update_zone(
    *,
    account_id: int,
    zone_id: int,
    name: str,
    is_outdoor: bool,
    color: str | None,
) -> bool:
    """Update zone name, is_outdoor flag, and color. Returns True if zone exists."""
    result = await db.execute(
        """
        UPDATE zone z
        SET name = $2, is_outdoor = $3, color = $4
        FROM location l
        WHERE z.id = $1 AND z.location_id = l.id AND l.account_id = $5
        """,
        zone_id,
        name,
        is_outdoor,
        color or None,
        account_id,
    )
    return result == "UPDATE 1"


async def get_zone_measurements(
    *, zone_id: int, attribute: Attribute, hours: int = 24
) -> list[tuple[datetime, float]]:
    """
    Get measurements for a zone within the last N hours.
    Returns list of (measured_at, value) tuples.
    Automatically joins through sensor_zone_assignment to get data from all
    sensors that were assigned to this zone during the time period.
    Excludes measurements in any exclusion ranges.
    """
    since = datetime.now() - timedelta(hours=hours)
    rows = await db.fetch(
        """
        SELECT m.measured_at, m.value
        FROM sensor_measurement m
        JOIN sensor_zone_assignment sza ON sza.sensor_id = m.sensor_id
        WHERE sza.zone_id = $1
          AND m.attribute = $2
          AND m.measured_at > $3
          AND sza.active_range @> m.measured_at
          AND NOT EXISTS (
              SELECT 1 FROM sensor_measurement_exclusion e
              WHERE e.sensor_id = m.sensor_id
                AND e.excluded @> m.measured_at
          )
        ORDER BY m.measured_at ASC
        """,
        zone_id,
        attribute,
        since,
    )
    return [(row["measured_at"], row["value"]) for row in rows]


async def get_zone_measurements_averaged(
    *,
    zone_id: int,
    attribute: Attribute,
    hours: int = 24,
    bucket_minutes: int = 60,
) -> list[tuple[datetime, float]]:
    """
    Get measurements for a zone within the last N hours, averaged over time buckets.
    Returns list of (bucket_start, avg_value) tuples.
    Automatically joins through sensor_zone_assignment to get data from all
    sensors that were assigned to this zone during the time period.
    Excludes measurements in any exclusion ranges.

    Args:
        zone_id: The zone to fetch measurements for.
        attribute: The measurement attribute (e.g., temperature).
        hours: Number of hours to look back.
        bucket_minutes: Size of time buckets in minutes for averaging.
    """
    since = datetime.now() - timedelta(hours=hours)
    rows = await db.fetch(
        """
        SELECT
            to_timestamp(
                floor(extract(epoch from m.measured_at) / ($4 * 60)) * ($4 * 60)
            ) AS bucket,
            avg(m.value) AS avg_value
        FROM sensor_measurement m
        JOIN sensor_zone_assignment sza ON sza.sensor_id = m.sensor_id
        WHERE sza.zone_id = $1
          AND m.attribute = $2
          AND m.measured_at > $3
          AND sza.active_range @> m.measured_at
          AND NOT EXISTS (
              SELECT 1 FROM sensor_measurement_exclusion e
              WHERE e.sensor_id = m.sensor_id
                AND e.excluded @> m.measured_at
          )
        GROUP BY bucket
        ORDER BY bucket ASC
        """,
        zone_id,
        attribute,
        since,
        bucket_minutes,
    )
    return [(row["bucket"], float(row["avg_value"])) for row in rows]


async def assign_sensor_to_zone(
    *, account_id: int, zone_id: int, sensor_id: int
) -> bool:
    """
    Assign a sensor to a zone, starting from now.

    If the sensor is currently assigned to another zone, ends that assignment first.
    Returns True if successful, False if zone or sensor doesn't exist.
    """
    # Verify zone and sensor belong to account
    check = await db.fetchrow(
        """
        SELECT
            EXISTS(
                SELECT 1 FROM zone z JOIN location l ON l.id = z.location_id
                WHERE z.id = $1 AND l.account_id = $3
            ) as zone_exists,
            EXISTS(
                SELECT 1 FROM sensor WHERE id = $2 AND account_id = $3
            ) as sensor_exists
        """,
        zone_id,
        sensor_id,
        account_id,
    )
    if not check or not check["zone_exists"] or not check["sensor_exists"]:
        return False

    # End any current assignment for this sensor
    await db.execute(
        """
        UPDATE sensor_zone_assignment
        SET active_range = tstzrange(lower(active_range), now(), '[)')
        WHERE sensor_id = $1 AND upper(active_range) IS NULL
        """,
        sensor_id,
    )

    # Create new assignment
    await db.execute(
        """
        INSERT INTO sensor_zone_assignment (zone_id, sensor_id, active_range)
        VALUES ($1, $2, tstzrange(now(), null, '[)'))
        """,
        zone_id,
        sensor_id,
    )
    return True


async def unassign_sensor(*, account_id: int, sensor_id: int) -> bool:
    """
    End the current zone assignment for a sensor (if any).
    Returns True if an assignment was ended.
    """
    result = await db.execute(
        """
        UPDATE sensor_zone_assignment sza
        SET active_range = tstzrange(lower(active_range), now(), '[)')
        FROM sensor s
        WHERE sza.sensor_id = $1
          AND sza.sensor_id = s.id
          AND s.account_id = $2
          AND upper(sza.active_range) IS NULL
        """,
        sensor_id,
        account_id,
    )
    return result == "UPDATE 1"


async def get_zone_assignments(
    *, account_id: int, zone_id: int
) -> list[tuple[int, int, str | None, datetime, datetime | None]]:
    """
    Get assignment history for a zone.
    Returns list of (assignment_id, sensor_id, sensor_name, start, end) tuples.
    End is None for currently active assignments.
    """
    rows = await db.fetch(
        """
        SELECT
            sza.id,
            sza.sensor_id,
            s.name as sensor_name,
            lower(sza.active_range) as start_time,
            upper(sza.active_range) as end_time
        FROM sensor_zone_assignment sza
        JOIN sensor s ON s.id = sza.sensor_id
        JOIN zone z ON z.id = sza.zone_id
        JOIN location l ON l.id = z.location_id
        WHERE sza.zone_id = $1 AND l.account_id = $2
        ORDER BY lower(sza.active_range) DESC
        """,
        zone_id,
        account_id,
    )
    return [
        (
            row["id"],
            row["sensor_id"],
            row["sensor_name"],
            row["start_time"],
            row["end_time"],
        )
        for row in rows
    ]


async def get_sensor_current_zone(
    *, account_id: int, sensor_id: int
) -> tuple[int, str] | None:
    """
    Get the current zone a sensor is assigned to.
    Returns (zone_id, zone_name) or None if not assigned.
    """
    row = await db.fetchrow(
        """
        SELECT z.id, z.name
        FROM sensor_zone_assignment sza
        JOIN zone z ON z.id = sza.zone_id
        JOIN location l ON l.id = z.location_id
        JOIN sensor s ON s.id = sza.sensor_id
        WHERE sza.sensor_id = $1
          AND s.account_id = $2
          AND sza.active_range @> now()::timestamptz
        """,
        sensor_id,
        account_id,
    )
    if not row:
        return None
    return (row["id"], row["name"])
