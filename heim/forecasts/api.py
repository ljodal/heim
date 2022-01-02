from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..auth.dependencies import current_account
from ..sensors.types import Attribute
from ..utils import timed
from .queries import get_forecast, get_instances

router = APIRouter()


class Forecast(BaseModel):
    created_at: datetime
    attribute: Attribute
    values: list[tuple[datetime, int]]


@router.get("/locations/{location_id}/forecasts", response_model=list[Forecast])
async def get_forecasts(
    *,
    account_id: int = Depends(current_account),
    location_id: int,
    attribute: Attribute,
) -> list[Forecast]:
    # TODO: Verify that forecast belongs to correct account

    forecast_id = await get_forecast(location_id=location_id, account_id=account_id)
    if not forecast_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No forecast found for location",
        )

    instances = await get_instances(forecast_id=forecast_id, attribute=attribute)

    with timed("Initialize response"):
        return [
            Forecast(created_at=created_at, attribute=attribute, values=list(values))
            for created_at, values in instances.items()
        ]
