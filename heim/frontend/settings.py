"""
Settings views for managing locations and integrations.
"""

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Path, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..accounts.queries import (
    create_location,
    get_location,
    get_locations,
    update_location,
)
from .dependencies import CurrentAccount
from .messages import Messages, get_messages

router = APIRouter(prefix="/settings")
templates = Jinja2Templates(directory="heim/frontend/templates")
templates.env.globals["get_messages"] = get_messages


###################
# Settings Index  #
###################


@router.get("/", response_class=HTMLResponse)
async def settings_index(
    request: Request,
    account_id: CurrentAccount,
) -> Response:
    """Main settings page."""
    locations = await get_locations(account_id=account_id)

    context = {
        "request": request,
        "locations": locations,
        "active_tab": "overview",
    }
    return templates.TemplateResponse("settings/index.html", context)


#####################
# Location Settings #
#####################


@router.get("/locations/", response_class=HTMLResponse)
async def locations_list(
    request: Request,
    account_id: CurrentAccount,
) -> Response:
    """List and manage locations."""
    locations = await get_locations(account_id=account_id)

    context = {
        "request": request,
        "locations": locations,
        "active_tab": "locations",
    }
    return templates.TemplateResponse("settings/locations.html", context)


@router.get("/locations/new/", response_class=HTMLResponse)
async def location_new(
    request: Request,
    account_id: CurrentAccount,
) -> Response:
    """Form to add a new location."""
    context = {
        "request": request,
        "active_tab": "locations",
    }
    return templates.TemplateResponse("settings/location_form.html", context)


@router.post("/locations/new/", response_class=RedirectResponse)
async def location_create(
    request: Request,
    account_id: CurrentAccount,
    messages: Messages,
    name: Annotated[str, Form()],
    latitude: Annotated[float, Form()],
    longitude: Annotated[float, Form()],
) -> RedirectResponse:
    """Create a new location."""
    await create_location(
        account_id=account_id,
        name=name,
        coordinate=(longitude, latitude),
    )
    messages.success(f"Location '{name}' created successfully!")
    return RedirectResponse(
        url="/settings/locations/", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/locations/{location_id}/", response_class=HTMLResponse)
async def location_detail(
    request: Request,
    account_id: CurrentAccount,
    location_id: Annotated[int, Path()],
) -> Response:
    """View location details."""
    location = await get_location(account_id=account_id, location_id=location_id)
    if location is None:
        raise HTTPException(status_code=404, detail="Location not found")

    context = {
        "request": request,
        "location": location,
        "active_tab": "locations",
    }
    return templates.TemplateResponse("settings/location_detail.html", context)


@router.post("/locations/{location_id}/", response_class=RedirectResponse)
async def location_update_view(
    request: Request,
    account_id: CurrentAccount,
    messages: Messages,
    location_id: Annotated[int, Path()],
    name: Annotated[str, Form()],
    latitude: Annotated[float, Form()],
    longitude: Annotated[float, Form()],
) -> RedirectResponse:
    """Update a location."""
    await update_location(
        account_id=account_id,
        location_id=location_id,
        name=name,
        coordinate=(longitude, latitude),
    )
    messages.success(f"Location '{name}' updated successfully!")
    return RedirectResponse(
        url="/settings/locations/", status_code=status.HTTP_303_SEE_OTHER
    )
