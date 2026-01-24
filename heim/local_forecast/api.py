"""
API endpoints for local forecast adjustments.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth.dependencies import current_account
from ..sensors.types import Attribute
from .queries import (
    get_bias_stats,
    get_forecast_and_sensor_for_location,
    get_latest_forecast_values,
)
from .stats import WelfordState, get_lead_time_bucket
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
    with local sensor observations. Returns the adjusted values along
    with uncertainty bounds.
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
    now = datetime.now(created_at.tzinfo)

    for measured_at, raw_value in forecast_values:
        # Calculate lead time in hours
        lead_time_hours = (measured_at - created_at).total_seconds() / 3600
        bucket = get_lead_time_bucket(lead_time_hours)

        # Get stats for this bucket, or use defaults
        stats = bias_stats.get(bucket, WelfordState())

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
                lead_time_bucket=bucket,
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

    Returns the current statistics for each lead time bucket, showing
    how much the forecast typically differs from observed values.
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
    from .. import db

    rows = await db.fetch(
        """
        SELECT lead_time_bucket, count, mean, m2, last_updated
        FROM forecast_bias_stats
        WHERE location_id = $1 AND forecast_id = $2 AND attribute = $3
        ORDER BY lead_time_bucket
        """,
        location_id,
        forecast_id,
        attribute,
    )

    return [
        BiasStats(
            lead_time_bucket=row["lead_time_bucket"],
            count=row["count"],
            mean=row["mean"],
            m2=row["m2"],
            last_updated=row["last_updated"],
        )
        for row in rows
    ]
