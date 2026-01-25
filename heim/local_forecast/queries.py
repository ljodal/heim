"""
Database queries for local forecast bias correction.
"""

from datetime import datetime

from .. import db
from ..sensors.types import Attribute
from .stats import BiasBucket, EWMAState, Season, TimeOfDay

# Default EWMA alpha (decay factor). With alpha=0.05, half-life is ~14 observations.
# If we get ~4 observations per day per bucket, this gives ~3.5 day half-life.
DEFAULT_ALPHA = 0.05

# Minimum number of samples required to use bucket-specific stats.
# Below this threshold, we fall back to less specific buckets or priors.
MIN_SAMPLE_COUNT = 5

# Default prior variance when we have no data (in 100x scaled units).
# 200 = 2°C standard deviation, which is a reasonable uninformative prior.
DEFAULT_PRIOR_VARIANCE = 200.0 * 200.0  # (2°C * 100)^2


async def get_bias_stats(
    *,
    location_id: int,
    forecast_id: int,
    attribute: Attribute,
) -> dict[int, EWMAState]:
    """
    Get bias statistics for all buckets.

    Returns a dict mapping bucket_key -> EWMAState.
    """

    rows = await db.fetch(
        """
        SELECT bucket, count, mean, var
        FROM forecast_bias_stats
        WHERE location_id = $1 AND forecast_id = $2 AND attribute = $3
        """,
        location_id,
        forecast_id,
        attribute,
    )

    return {
        row["bucket"]: EWMAState(
            alpha=DEFAULT_ALPHA,
            count=row["count"],
            mean=row["mean"],
            var=row["var"],
        )
        for row in rows
    }


def get_fallback_buckets(bucket: BiasBucket) -> list[int]:
    """
    Get a list of bucket keys to try, from most to least specific.

    Fallback hierarchy:
    1. Exact bucket (lead_time + season + time_of_day)
    2. Same lead_time + season, any time_of_day
    3. Same lead_time, any season/time_of_day
    """
    fallbacks = [bucket.to_db_key()]

    # Add same lead_time + season, different times of day
    for tod in TimeOfDay:
        if tod != bucket.time_of_day:
            alt = BiasBucket(
                lead_time=bucket.lead_time,
                season=bucket.season,
                time_of_day=tod,
            )
            fallbacks.append(alt.to_db_key())

    # Add same lead_time, different seasons
    for season in Season:
        if season != bucket.season:
            for tod in TimeOfDay:
                alt = BiasBucket(
                    lead_time=bucket.lead_time,
                    season=season,
                    time_of_day=tod,
                )
                fallbacks.append(alt.to_db_key())

    return fallbacks


def lookup_with_fallback(
    bucket: BiasBucket,
    stats: dict[int, EWMAState],
    min_count: int = MIN_SAMPLE_COUNT,
) -> EWMAState:
    """
    Look up stats for a bucket with fallback to less specific buckets.

    If the exact bucket has insufficient data, tries progressively less
    specific buckets. If none have enough data, returns a prior with
    high uncertainty.
    """
    fallbacks = get_fallback_buckets(bucket)

    # Try each fallback in order
    for bucket_key in fallbacks:
        if bucket_key in stats and stats[bucket_key].count >= min_count:
            return stats[bucket_key]

    # No bucket has enough data - aggregate what we have for this lead time
    lead_time_stats = [
        s
        for key, s in stats.items()
        if BiasBucket.from_db_key(key).lead_time == bucket.lead_time and s.count > 0
    ]

    if lead_time_stats:
        # Weighted average of available stats for this lead time
        total_count = sum(s.count for s in lead_time_stats)
        if total_count > 0:
            # Weight by effective sample size
            weighted_mean = sum(s.mean * s.count for s in lead_time_stats) / total_count
            # Use max variance (conservative)
            max_var = max(s.var for s in lead_time_stats) if lead_time_stats else 0
            # Use max variance (conservative), with a floor for uncertainty
            min_var = DEFAULT_PRIOR_VARIANCE / 4
            return EWMAState(
                alpha=DEFAULT_ALPHA,
                count=total_count,
                mean=weighted_mean,
                var=max(max_var, min_var),
            )

    # No data at all - return uninformative prior
    return EWMAState(
        alpha=DEFAULT_ALPHA,
        count=0,
        mean=0.0,  # No bias correction
        var=DEFAULT_PRIOR_VARIANCE,  # High uncertainty
    )


async def upsert_bias_stats(
    *,
    location_id: int,
    sensor_id: int,
    forecast_id: int,
    attribute: Attribute,
    bucket: BiasBucket,
    state: EWMAState,
) -> None:
    """
    Insert or update bias statistics for a specific bucket.

    For EWMA, we simply replace the old state with the new one
    (the exponential weighting is applied during the update phase).
    """

    bucket_key = bucket.to_db_key()

    await db.execute(
        """
        INSERT INTO forecast_bias_stats (
            location_id, sensor_id, forecast_id, attribute,
            bucket, count, mean, var, last_updated
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, now())
        ON CONFLICT (location_id, sensor_id, forecast_id, attribute, bucket)
        DO UPDATE SET
            count = EXCLUDED.count,
            mean = EXCLUDED.mean,
            var = EXCLUDED.var,
            last_updated = now()
        """,
        location_id,
        sensor_id,
        forecast_id,
        attribute,
        bucket_key,
        state.count,
        state.mean,
        state.var,
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
    tolerance_minutes: int = 30,
) -> list[tuple[datetime, datetime, int, int]]:
    """
    Get paired forecast and observation values for analysis.

    Uses a time window to match sensor readings to forecast timestamps,
    selecting the closest reading within the tolerance window.

    Args:
        forecast_id: The forecast to analyze
        sensor_id: The sensor providing observations
        attribute: The attribute to compare (e.g., temperature)
        since: Only include data after this time
        tolerance_minutes: Maximum time difference for matching (default 30 min)

    Returns:
        List of (forecast_created_at, measured_at, forecast_value, observed_value).
        The difference (forecast_value - observed_value) is the error to track.
    """

    since_clause = ""
    args: list[object] = [forecast_id, sensor_id, attribute, tolerance_minutes]

    if since:
        since_clause = "AND fi.created_at > $5"
        args.append(since)

    # Use a lateral join to find the closest sensor reading within the tolerance
    rows = await db.fetch(
        f"""
        SELECT DISTINCT ON (fi.id, fv.measured_at)
            fi.created_at AS forecast_created_at,
            fv.measured_at,
            fv.value AS forecast_value,
            sm.value AS observed_value,
            ABS(EXTRACT(EPOCH FROM (sm.measured_at - fv.measured_at))) AS time_diff
        FROM forecast_instance fi
        JOIN forecast_value fv ON fv.forecast_instance_id = fi.id
        JOIN sensor_measurement sm ON (
            sm.sensor_id = $2
            AND sm.attribute = $3
            AND sm.measured_at BETWEEN
                fv.measured_at - ($4 || ' minutes')::interval
                AND fv.measured_at + ($4 || ' minutes')::interval
        )
        WHERE fi.forecast_id = $1 AND fv.attribute = $3 {since_clause}
        ORDER BY fi.id, fv.measured_at, time_diff
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


async def get_existing_stats(
    *,
    location_id: int,
    forecast_id: int,
    attribute: Attribute,
) -> dict[int, EWMAState]:
    """
    Get all existing EWMA states for a location/forecast/attribute.

    Returns a dict mapping bucket_key -> EWMAState.
    """
    rows = await db.fetch(
        """
        SELECT bucket, count, mean, var
        FROM forecast_bias_stats
        WHERE location_id = $1 AND forecast_id = $2 AND attribute = $3
        """,
        location_id,
        forecast_id,
        attribute,
    )

    return {
        row["bucket"]: EWMAState(
            alpha=DEFAULT_ALPHA,
            count=row["count"],
            mean=row["mean"],
            var=row["var"],
        )
        for row in rows
    }
