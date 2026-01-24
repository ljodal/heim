"""
Background tasks for computing and updating forecast bias statistics.
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone

import structlog

from ..sensors.types import Attribute
from ..tasks import task
from .queries import (
    get_forecast_and_sensor_for_location,
    get_last_processed_time,
    get_paired_observations,
    upsert_bias_stats,
)
from .stats import WelfordState, get_lead_time_bucket

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
    1. Finds paired forecast/observation data since the last update
    2. Groups errors by lead time bucket
    3. Updates the running statistics using Welford's algorithm
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

    # Get the last time we processed data (to avoid reprocessing)
    last_processed = await get_last_processed_time(
        location_id=location_id,
        forecast_id=forecast_id,
        attribute=attr,
    )

    # Get paired observations since last update
    pairs = await get_paired_observations(
        forecast_id=forecast_id,
        sensor_id=sensor_id,
        attribute=attr,
        since=last_processed,
    )

    if not pairs:
        logger.info(
            "No new paired observations to process",
            location_id=location_id,
            forecast_id=forecast_id,
        )
        return

    logger.info(
        "Processing paired observations",
        count=len(pairs),
        location_id=location_id,
    )

    # Group errors by lead time bucket and compute statistics
    bucket_stats: dict[int, WelfordState] = defaultdict(WelfordState)

    for forecast_created_at, measured_at, forecast_value, observed_value in pairs:
        # Calculate lead time in hours
        lead_time = (measured_at - forecast_created_at).total_seconds() / 3600
        bucket = get_lead_time_bucket(lead_time)

        # Error = forecast - observed (positive means forecast was too high)
        error = forecast_value - observed_value
        bucket_stats[bucket].update(float(error))

    # Update the database with new statistics
    for bucket, state in bucket_stats.items():
        await upsert_bias_stats(
            location_id=location_id,
            sensor_id=sensor_id,
            forecast_id=forecast_id,
            attribute=attr,
            lead_time_bucket=bucket,
            state=state,
        )
        logger.info(
            "Updated bias stats",
            bucket=bucket,
            count=state.count,
            mean=round(state.mean, 2),
            std_dev=round(state.std_dev, 2),
        )

    # Schedule next update in 1 hour
    next_run = datetime.now(timezone.utc) + timedelta(hours=1)
    await update_forecast_bias_stats.defer(
        arguments={
            "account_id": account_id,
            "location_id": location_id,
            "attribute": attribute,
        },
        run_at=next_run,
    )
