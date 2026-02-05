from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth.dependencies import current_account
from .models import SensorHistory, TemperatureChartData
from .selectors import get_temperature_chart_data, get_temperature_history

router = APIRouter()


@router.get(
    "/locations/{location_id}/temperature-chart",
    response_model=TemperatureChartData,
)
async def temperature_chart(
    location_id: int,
    account_id: int = Depends(current_account),
) -> TemperatureChartData:
    """
    Get temperature chart data for a location.

    Uses the first outdoor sensor for the location.
    Returns 48 hours of historical temperature readings (15-minute buckets)
    and up to 3 forecast instances (latest, 12h old, 24h old).
    """
    data = await get_temperature_chart_data(
        account_id=account_id, location_id=location_id
    )
    if not data:
        raise HTTPException(
            status_code=404, detail="Location or outdoor sensor not found"
        )
    return data


@router.get(
    "/locations/{location_id}/temperature-history",
    response_model=list[SensorHistory],
)
async def temperature_history(
    location_id: int,
    account_id: int = Depends(current_account),
    days: int = Query(default=7, ge=1, le=365),
) -> list[SensorHistory]:
    """
    Get temperature history for all sensors at a location.

    Returns readings for each sensor, averaged over 15-minute buckets.
    """
    return await get_temperature_history(
        account_id=account_id, location_id=location_id, days=days
    )
