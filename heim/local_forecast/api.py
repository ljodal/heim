"""
API endpoints for local forecast adjustments.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from .. import db
from ..auth.dependencies import current_account
from ..sensors.types import Attribute
from .queries import (
    DEFAULT_ALPHA,
    get_bias_stats,
    get_forecast_and_sensor_for_location,
    get_latest_forecast_values,
)
from .stats import BiasBucket, EWMAState
from .types import AdjustedForecast, AdjustedForecastValue, BiasStats

router = APIRouter()


@router.get(
    "/locations/{location_id}/adjusted-forecast",
    response_model=AdjustedForecast,
)
async def get_adjusted_forecast(
    *,
    account_id: int = Depends(current_account),
    location_id: int,
    attribute: Attribute = Attribute.AIR_TEMPERATURE,
) -> AdjustedForecast:
    """
    Get a bias-corrected forecast for a location.

    The adjustment is based on historical comparison of yr.no forecasts
    with local sensor observations, using exponentially weighted statistics.
    Bias is tracked separately by lead time, season, and time of day.
    """

    # Get forecast and sensor for this location
    result = await get_forecast_and_sensor_for_location(
        account_id=account_id,
        location_id=location_id,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No forecast or sensor found for location",
        )

    forecast_id, sensor_id = result

    # Get the latest forecast values
    forecast_result = await get_latest_forecast_values(
        forecast_id=forecast_id,
        attribute=attribute,
    )

    if not forecast_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No forecast values found",
        )

    created_at, forecast_values = forecast_result

    # Get bias statistics for all buckets
    bias_stats = await get_bias_stats(
        location_id=location_id,
        forecast_id=forecast_id,
        attribute=attribute,
    )

    # Apply bias correction to each forecast value
    adjusted_values: list[AdjustedForecastValue] = []

    for measured_at, raw_value in forecast_values:
        # Determine the bucket for this forecast point
        bucket = BiasBucket.from_timestamps(created_at, measured_at)
        bucket_key = bucket.to_db_key()

        # Calculate lead time in hours
        lead_time_hours = (measured_at - created_at).total_seconds() / 3600

        # Get stats for this bucket, or use defaults
        stats = bias_stats.get(bucket_key, EWMAState(alpha=DEFAULT_ALPHA))

        # Apply bias correction: adjusted = raw - mean_error
        adjusted_value = round(raw_value - stats.mean)
        std_error = stats.std_dev

        adjusted_values.append(
            AdjustedForecastValue(
                measured_at=measured_at,
                raw_value=raw_value,
                adjusted_value=adjusted_value,
                std_error=std_error,
                lead_time_hours=lead_time_hours,
                bucket=bucket_key,
                sample_count=stats.count,
            )
        )

    return AdjustedForecast(
        forecast_id=forecast_id,
        sensor_id=sensor_id,
        location_id=location_id,
        attribute=attribute,
        created_at=created_at,
        values=adjusted_values,
    )


@router.get(
    "/locations/{location_id}/forecast-bias",
    response_model=list[BiasStats],
)
async def get_forecast_bias(
    *,
    account_id: int = Depends(current_account),
    location_id: int,
    attribute: Attribute = Attribute.AIR_TEMPERATURE,
) -> list[BiasStats]:
    """
    Get the bias statistics for a location.

    Returns the current statistics for each bucket (lead time + season + time of day),
    showing how much the forecast typically differs from observed values.
    """

    # Get forecast for this location
    result = await get_forecast_and_sensor_for_location(
        account_id=account_id,
        location_id=location_id,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No forecast found for location",
        )

    forecast_id, _ = result

    # Get bias statistics
    rows = await db.fetch(
        """
        SELECT bucket, count, mean, var, last_updated
        FROM forecast_bias_stats
        WHERE location_id = $1 AND forecast_id = $2 AND attribute = $3
        ORDER BY bucket
        """,
        location_id,
        forecast_id,
        attribute,
    )

    stats_list = []
    for row in rows:
        bucket = BiasBucket.from_db_key(row["bucket"])
        stats_list.append(
            BiasStats(
                bucket=row["bucket"],
                lead_time=bucket.lead_time,
                season=bucket.season,
                time_of_day=bucket.time_of_day,
                count=row["count"],
                mean=row["mean"],
                var=row["var"],
                last_updated=row["last_updated"],
            )
        )

    return stats_list
