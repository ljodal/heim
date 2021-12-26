from fastapi import APIRouter, Depends

from .dependencies import current_account
from .models import Location
from .queries import get_locations

router = APIRouter()


@router.get("/locations", response_model=list[Location])
async def _get_locations(account_id: int = Depends(current_account)) -> list[Location]:
    return await get_locations(account_id=account_id)
