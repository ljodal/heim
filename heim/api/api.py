from fastapi import APIRouter, Depends, HTTPException

from ..auth.dependencies import current_account
from .models import TemperatureChartData
from .selectors import get_temperature_chart_data

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
