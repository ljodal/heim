"""
Database queries for local forecast bias correction.
"""

from datetime import datetime

from .. import db
from ..sensors.types import Attribute
from .stats import WelfordState


async def get_bias_stats(
    *,
    location_id: int,
    forecast_id: int,
    attribute: Attribute,
) -> dict[int, WelfordState]:
    """
    Get bias statistics for all lead time buckets.

    Returns a dict mapping lead_time_bucket -> WelfordState.
    """

    rows = await db.fetch(
        """
        SELECT lead_time_bucket, count, mean, m2
        FROM forecast_bias_stats
        WHERE location_id = $1 AND forecast_id = $2 AND attribute = $3
        """,
        location_id,
        forecast_id,
        attribute,
    )

    return {
        row["lead_time_bucket"]: WelfordState(
            count=row["count"],
            mean=row["mean"],
            m2=row["m2"],
        )
        for row in rows
    }


async def upsert_bias_stats(
    *,
    location_id: int,
    sensor_id: int,
    forecast_id: int,
    attribute: Attribute,
    lead_time_bucket: int,
    state: WelfordState,
) -> None:
    """
    Insert or update bias statistics for a specific bucket.

    Uses Welford's merge algorithm to combine with existing stats.
    """

    await db.execute(
        """
        INSERT INTO forecast_bias_stats (
            location_id, sensor_id, forecast_id, attribute,
            lead_time_bucket, count, mean, m2, last_updated
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, now())
        ON CONFLICT (location_id, sensor_id, forecast_id, attribute, lead_time_bucket)
        DO UPDATE SET
            count = forecast_bias_stats.count + EXCLUDED.count,
            mean = forecast_bias_stats.mean + (
                (EXCLUDED.mean - forecast_bias_stats.mean) * EXCLUDED.count
                / (forecast_bias_stats.count + EXCLUDED.count)
            ),
            m2 = forecast_bias_stats.m2 + EXCLUDED.m2 + (
                (EXCLUDED.mean - forecast_bias_stats.mean)
                * (EXCLUDED.mean - forecast_bias_stats.mean)
                * forecast_bias_stats.count * EXCLUDED.count
                / (forecast_bias_stats.count + EXCLUDED.count)
            ),
            last_updated = now()
        """,
        location_id,
        sensor_id,
        forecast_id,
        attribute,
        lead_time_bucket,
        state.count,
        state.mean,
        state.m2,
    )


async def get_forecast_and_sensor_for_location(
    *,
    account_id: int,
    location_id: int,
) -> tuple[int, int] | None:
    """
    Get the forecast and sensor IDs for a location.

    Returns the first forecast and sensor found at the location.
    """

    row = await db.fetchrow(
        """
        SELECT
            (
                SELECT id FROM forecast
                WHERE location_id = $1 AND account_id = $2 LIMIT 1
            ),
            (
                SELECT id FROM sensor
                WHERE location_id = $1 AND account_id = $2 LIMIT 1
            )
        """,
        location_id,
        account_id,
    )

    if row and row[0] and row[1]:
        return (row[0], row[1])
    return None


async def get_paired_observations(
    *,
    forecast_id: int,
    sensor_id: int,
    attribute: Attribute,
    since: datetime | None = None,
) -> list[tuple[datetime, datetime, int, int]]:
    """
    Get paired forecast and observation values for analysis.

    Returns list of (forecast_created_at, measured_at, forecast_value, observed_value).
    The difference (forecast_value - observed_value) is the error to track.
    """

    since_clause = ""
    args: list[object] = [forecast_id, sensor_id, attribute]

    if since:
        since_clause = "AND fi.created_at > $4"
        args.append(since)

    rows = await db.fetch(
        f"""
        SELECT
            fi.created_at AS forecast_created_at,
            fv.measured_at,
            fv.value AS forecast_value,
            sm.value AS observed_value
        FROM forecast_instance fi
        JOIN forecast_value fv ON fv.forecast_instance_id = fi.id
        JOIN sensor_measurement sm ON (
            sm.sensor_id = $2
            AND sm.attribute = $3
            AND sm.measured_at = fv.measured_at
        )
        WHERE fi.forecast_id = $1 AND fv.attribute = $3 {since_clause}
        ORDER BY fi.created_at, fv.measured_at
        """,
        *args,
    )

    return [
        (
            row["forecast_created_at"],
            row["measured_at"],
            row["forecast_value"],
            row["observed_value"],
        )
        for row in rows
    ]


async def get_latest_forecast_values(
    *,
    forecast_id: int,
    attribute: Attribute,
) -> tuple[datetime, list[tuple[datetime, int]]] | None:
    """
    Get the latest forecast instance and its values.

    Returns (created_at, [(measured_at, value), ...]) or None if no forecast exists.
    """

    # Get the latest forecast instance
    instance = await db.fetchrow(
        """
        SELECT id, created_at
        FROM forecast_instance
        WHERE forecast_id = $1
        ORDER BY created_at DESC
        LIMIT 1
        """,
        forecast_id,
    )

    if not instance:
        return None

    # Get all values for this instance
    rows = await db.fetch(
        """
        SELECT measured_at, value
        FROM forecast_value
        WHERE forecast_instance_id = $1 AND attribute = $2
        ORDER BY measured_at
        """,
        instance["id"],
        attribute,
    )

    return (
        instance["created_at"],
        [(row["measured_at"], row["value"]) for row in rows],
    )


async def get_last_processed_time(
    *,
    location_id: int,
    forecast_id: int,
    attribute: Attribute,
) -> datetime | None:
    """
    Get the last time bias stats were updated for this combination.

    This helps avoid reprocessing the same data.
    """

    return await db.fetchval(
        """
        SELECT MAX(last_updated)
        FROM forecast_bias_stats
        WHERE location_id = $1 AND forecast_id = $2 AND attribute = $3
        """,
        location_id,
        forecast_id,
        attribute,
    )
