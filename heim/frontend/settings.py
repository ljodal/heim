"""
Settings views for managing locations and integrations.
"""

import os
from typing import Annotated, Any
from urllib.parse import urlencode

from fastapi import APIRouter, Form, HTTPException, Path, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .. import db
from ..accounts.queries import (
    create_location,
    get_location,
    get_locations,
    update_location,
)
from ..integrations.netatmo.client import NetatmoClient
from ..integrations.netatmo.queries import (
    create_netatmo_sensor,
    get_netatmo_account_info,
    get_netatmo_sensor_device_id,
    get_netatmo_sensors,
    has_netatmo_account,
)
from ..integrations.netatmo.services import with_netatmo_client
from ..integrations.netatmo.tasks import update_sensor_data as update_netatmo_sensor_data
from .dependencies import CurrentAccount
from .messages import Messages, get_messages

router = APIRouter(prefix="/settings")
templates = Jinja2Templates(directory="heim/frontend/templates")
templates.env.globals["get_messages"] = get_messages


def is_netatmo_configured() -> bool:
    """Check if Netatmo integration is configured via environment variables."""
    return bool(os.getenv("NETATMO_CLIENT_ID"))


# Make configuration check available in templates
templates.env.globals["is_netatmo_configured"] = is_netatmo_configured


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

    # Get Netatmo account info if configured
    netatmo_configured = is_netatmo_configured()
    netatmo_account = None
    if netatmo_configured:
        account_info = await get_netatmo_account_info(account_id=account_id)
        if account_info:
            netatmo_account = {"id": account_info[0], "expires_at": account_info[1]}

    context = {
        "request": request,
        "locations": locations,
        "netatmo_configured": netatmo_configured,
        "netatmo_account": netatmo_account,
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


####################
# Netatmo Settings #
####################


@router.get("/netatmo/", response_class=HTMLResponse)
async def netatmo_index(
    request: Request,
    account_id: CurrentAccount,
) -> Response:
    """Netatmo integration settings."""
    if not is_netatmo_configured():
        raise HTTPException(status_code=404, detail="Netatmo integration not configured")

    account_info = await get_netatmo_account_info(account_id=account_id)
    netatmo_account = None
    if account_info:
        netatmo_account = {"id": account_info[0], "expires_at": account_info[1]}

    sensors = await get_netatmo_sensors(account_id=account_id) if netatmo_account else []
    locations = await get_locations(account_id=account_id)

    context = {
        "request": request,
        "netatmo_account": netatmo_account,
        "sensors": sensors,
        "locations": locations,
        "active_tab": "netatmo",
    }
    return templates.TemplateResponse("settings/netatmo.html", context)


@router.get("/netatmo/link/", response_class=RedirectResponse)
async def netatmo_link(
    request: Request,
    account_id: CurrentAccount,
) -> RedirectResponse:
    """Redirect to Netatmo OAuth."""
    client_id = os.getenv("NETATMO_CLIENT_ID")
    if not client_id:
        raise HTTPException(
            status_code=500, detail="NETATMO_CLIENT_ID not configured"
        )

    redirect_uri = os.getenv(
        "NETATMO_REDIRECT_URI", "http://localhost:8000/api/netatmo/callback"
    )

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "read_station",
        "state": str(account_id),
    }

    auth_url = f"https://api.netatmo.com/oauth2/authorize?{urlencode(params)}"
    return RedirectResponse(url=auth_url, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/netatmo/devices/", response_class=HTMLResponse)
async def netatmo_devices(
    request: Request,
    account_id: CurrentAccount,
) -> Response:
    """List available Netatmo devices."""
    if not await has_netatmo_account(account_id=account_id):
        return RedirectResponse(
            url="/settings/netatmo/", status_code=status.HTTP_303_SEE_OTHER
        )

    # Get devices from Netatmo API
    stations = await _get_netatmo_stations(account_id=account_id)

    # Get already registered sensors to mark them
    registered_sensors = await get_netatmo_sensors(account_id=account_id)
    registered_ids: set[str | None] = set()
    for sensor_id, _, _ in registered_sensors:
        device_id = await get_netatmo_sensor_device_id(sensor_id=sensor_id)
        registered_ids.add(device_id)

    locations = await get_locations(account_id=account_id)

    context = {
        "request": request,
        "stations": stations,
        "registered_ids": registered_ids,
        "locations": locations,
        "active_tab": "netatmo",
    }
    return templates.TemplateResponse("settings/netatmo_devices.html", context)


@with_netatmo_client
async def _get_netatmo_stations(
    client: NetatmoClient, *, account_id: int
) -> list[Any]:
    """Fetch stations from Netatmo API."""
    data = await client.get_stations_data()
    return data.devices


@router.post("/netatmo/devices/add/", response_class=RedirectResponse)
async def netatmo_add_device(
    request: Request,
    account_id: CurrentAccount,
    messages: Messages,
    device_id: Annotated[str, Form()],
    device_name: Annotated[str, Form()],
    module_type: Annotated[str, Form()],
    station_id: Annotated[str, Form()],
    location_id: Annotated[int, Form()],
) -> RedirectResponse:
    """Add a Netatmo device as a sensor."""
    try:
        async with db.transaction():
            sensor_id = await create_netatmo_sensor(
                account_id=account_id,
                name=device_name,
                location_id=location_id,
                module_type=module_type,
                netatmo_id=device_id,
                station_id=station_id,
            )

            await update_netatmo_sensor_data(
                account_id=account_id, sensor_id=sensor_id
            ).schedule(cron_expression="*/10 * * * *")

        messages.success(f"Sensor '{device_name}' added successfully!")
    except Exception as e:
        messages.error(f"Failed to add sensor: {e}")

    return RedirectResponse(
        url="/settings/netatmo/", status_code=status.HTTP_303_SEE_OTHER
    )
