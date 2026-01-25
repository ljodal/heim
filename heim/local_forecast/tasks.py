"""
Background tasks for computing and updating forecast bias statistics.
"""

from collections import defaultdict
from datetime import UTC, datetime, timedelta

import structlog

from ..sensors.types import Attribute
from ..tasks import task
from .queries import (
    DEFAULT_ALPHA,
    get_existing_stats,
    get_forecast_and_sensor_for_location,
    get_paired_observations,
    upsert_bias_stats,
)
from .stats import BiasBucket, EWMAState

logger = structlog.get_logger()


@task(name="update-forecast-bias-stats", atomic=True)
async def update_forecast_bias_stats(
    *,
    account_id: int,
    location_id: int,
    attribute: str = "air temperature",
) -> None:
    """
    Update bias statistics for a location by comparing forecasts with observations.

    This task:
    1. Finds paired forecast/observation data
    2. Groups errors by bucket (lead time + season + time of day)
    3. Updates the EWMA statistics for each bucket
    """

    attr = Attribute(attribute)

    # Get forecast and sensor for this location
    result = await get_forecast_and_sensor_for_location(
        account_id=account_id,
        location_id=location_id,
    )

    if not result:
        logger.warning(
            "No forecast or sensor found for location",
            location_id=location_id,
        )
        return

    forecast_id, sensor_id = result

    # Get existing stats to continue from
    existing_stats = await get_existing_stats(
        location_id=location_id,
        forecast_id=forecast_id,
        attribute=attr,
    )

    # Get paired observations (we process all available data each time,
    # EWMA naturally down-weights older observations)
    pairs = await get_paired_observations(
        forecast_id=forecast_id,
        sensor_id=sensor_id,
        attribute=attr,
    )

    if not pairs:
        logger.info(
            "No paired observations to process",
            location_id=location_id,
            forecast_id=forecast_id,
        )
        return

    logger.info(
        "Processing paired observations",
        count=len(pairs),
        location_id=location_id,
    )

    # Group observations by bucket and compute EWMA stats
    # We need to process in chronological order for EWMA to work correctly
    bucket_stats: dict[int, EWMAState] = defaultdict(
        lambda: EWMAState(alpha=DEFAULT_ALPHA)
    )

    # Start with existing stats
    for bucket_key, state in existing_stats.items():
        bucket_stats[bucket_key] = state

    # Process observations in order
    for forecast_created_at, measured_at, forecast_value, observed_value in pairs:
        bucket = BiasBucket.from_timestamps(forecast_created_at, measured_at)
        bucket_key = bucket.to_db_key()

        # Error = forecast - observed (positive means forecast was too high)
        error = float(forecast_value - observed_value)

        # Get or create state for this bucket
        if bucket_key not in bucket_stats:
            bucket_stats[bucket_key] = EWMAState(alpha=DEFAULT_ALPHA)

        bucket_stats[bucket_key].update(error)

    # Save updated stats
    buckets_updated = 0
    for bucket_key, state in bucket_stats.items():
        bucket = BiasBucket.from_db_key(bucket_key)
        await upsert_bias_stats(
            location_id=location_id,
            sensor_id=sensor_id,
            forecast_id=forecast_id,
            attribute=attr,
            bucket=bucket,
            state=state,
        )
        buckets_updated += 1

    logger.info(
        "Updated bias stats",
        buckets_updated=buckets_updated,
        total_observations=len(pairs),
    )

    # Schedule next update in 1 hour
    next_run = datetime.now(UTC) + timedelta(hours=1)
    await update_forecast_bias_stats.defer(
        arguments={
            "account_id": account_id,
            "location_id": location_id,
            "attribute": attribute,
        },
        run_at=next_run,
    )
