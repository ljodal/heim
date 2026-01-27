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
from ..forecasts.queries import (
    get_all_forecasts,
    get_forecast_by_id,
    update_forecast,
)
from ..integrations.netatmo.client import NetatmoClient
from ..integrations.netatmo.queries import (
    create_netatmo_sensor,
    get_netatmo_account_info,
    get_netatmo_sensor_device_id,
    get_netatmo_sensors,
    has_netatmo_account,
)
from ..integrations.netatmo.tasks import (
    update_sensor_data as update_netatmo_sensor_data,
)
from ..sensors.queries import (
    get_all_sensors,
    get_sensor,
    update_sensor,
)
from ..zones.queries import (
    assign_sensor_to_zone,
    create_zone,
    get_all_zones,
    get_sensor_current_zone,
    get_zone,
    get_zone_assignments,
    unassign_sensor,
    update_zone,
)
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
        "locations": locations,
        "netatmo_configured": netatmo_configured,
        "netatmo_account": netatmo_account,
        "active_tab": "overview",
    }
    return templates.TemplateResponse(request, "settings/index.html", context)


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
        "locations": locations,
        "active_tab": "locations",
    }
    return templates.TemplateResponse(request, "settings/locations.html", context)


@router.get("/locations/new/", response_class=HTMLResponse)
async def location_new(
    request: Request,
    account_id: CurrentAccount,
) -> Response:
    """Form to add a new location."""
    return templates.TemplateResponse(
        request, "settings/location_form.html", {"active_tab": "locations"}
    )


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
        "location": location,
        "active_tab": "locations",
    }
    return templates.TemplateResponse(request, "settings/location_detail.html", context)


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
        raise HTTPException(
            status_code=404, detail="Netatmo integration not configured"
        )

    account_info = await get_netatmo_account_info(account_id=account_id)
    netatmo_account = None
    if account_info:
        netatmo_account = {"id": account_info[0], "expires_at": account_info[1]}

    sensors = (
        await get_netatmo_sensors(account_id=account_id) if netatmo_account else []
    )
    locations = await get_locations(account_id=account_id)

    context = {
        "netatmo_account": netatmo_account,
        "sensors": sensors,
        "locations": locations,
        "active_tab": "netatmo",
    }
    return templates.TemplateResponse(request, "settings/netatmo.html", context)


@router.get("/netatmo/link/", response_class=RedirectResponse)
async def netatmo_link(
    request: Request,
    account_id: CurrentAccount,
) -> RedirectResponse:
    """Redirect to Netatmo OAuth."""
    client_id = os.getenv("NETATMO_CLIENT_ID")
    if not client_id:
        raise HTTPException(status_code=500, detail="NETATMO_CLIENT_ID not configured")

    redirect_uri = str(request.url_for("oauth_callback"))

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
        "stations": stations,
        "registered_ids": registered_ids,
        "locations": locations,
        "active_tab": "netatmo",
    }
    return templates.TemplateResponse(request, "settings/netatmo_devices.html", context)


@NetatmoClient.authenticated()
async def _get_netatmo_stations(client: NetatmoClient, *, account_id: int) -> list[Any]:
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


###################
# Sensor Settings #
###################


@router.get("/sensors/", response_class=HTMLResponse)
async def sensors_list(
    request: Request,
    account_id: CurrentAccount,
) -> Response:
    """List and manage sensors."""
    sensors = await get_all_sensors(account_id=account_id)

    context = {
        "sensors": sensors,
        "active_tab": "sensors",
    }
    return templates.TemplateResponse(request, "settings/sensors.html", context)


@router.get("/sensors/{sensor_id}/", response_class=HTMLResponse)
async def sensor_detail(
    request: Request,
    account_id: CurrentAccount,
    sensor_id: Annotated[int, Path()],
) -> Response:
    """View sensor details."""
    sensor_data = await get_sensor(account_id=account_id, sensor_id=sensor_id)
    if sensor_data is None:
        raise HTTPException(status_code=404, detail="Sensor not found")

    sensor = {
        "id": sensor_data[0],
        "name": sensor_data[1],
        "location_id": sensor_data[2],
        "location_name": sensor_data[3],
    }

    # Get current zone assignment
    current_zone_data = await get_sensor_current_zone(
        account_id=account_id, sensor_id=sensor_id
    )
    current_zone = None
    if current_zone_data:
        current_zone = {"id": current_zone_data[0], "name": current_zone_data[1]}

    context = {
        "sensor": sensor,
        "current_zone": current_zone,
        "active_tab": "sensors",
    }
    return templates.TemplateResponse(request, "settings/sensor_detail.html", context)


@router.post("/sensors/{sensor_id}/", response_class=RedirectResponse)
async def sensor_update_view(
    request: Request,
    account_id: CurrentAccount,
    messages: Messages,
    sensor_id: Annotated[int, Path()],
    name: Annotated[str, Form()],
) -> RedirectResponse:
    """Update a sensor."""
    await update_sensor(account_id=account_id, sensor_id=sensor_id, name=name)
    messages.success(f"Sensor '{name}' updated successfully!")
    return RedirectResponse(
        url="/settings/sensors/", status_code=status.HTTP_303_SEE_OTHER
    )


#####################
# Forecast Settings #
#####################


@router.get("/forecasts/", response_class=HTMLResponse)
async def forecasts_list(
    request: Request,
    account_id: CurrentAccount,
) -> Response:
    """List and manage forecasts."""
    forecasts = await get_all_forecasts(account_id=account_id)

    context = {
        "forecasts": forecasts,
        "active_tab": "forecasts",
    }
    return templates.TemplateResponse(request, "settings/forecasts.html", context)


@router.get("/forecasts/{forecast_id}/", response_class=HTMLResponse)
async def forecast_detail(
    request: Request,
    account_id: CurrentAccount,
    forecast_id: Annotated[int, Path()],
) -> Response:
    """View forecast details."""
    forecast_data = await get_forecast_by_id(
        account_id=account_id, forecast_id=forecast_id
    )
    if forecast_data is None:
        raise HTTPException(status_code=404, detail="Forecast not found")

    forecast = {
        "id": forecast_data[0],
        "name": forecast_data[1],
        "location_id": forecast_data[2],
        "location_name": forecast_data[3],
    }

    context = {
        "forecast": forecast,
        "active_tab": "forecasts",
    }
    return templates.TemplateResponse(request, "settings/forecast_detail.html", context)


@router.post("/forecasts/{forecast_id}/", response_class=RedirectResponse)
async def forecast_update_view(
    request: Request,
    account_id: CurrentAccount,
    messages: Messages,
    forecast_id: Annotated[int, Path()],
    name: Annotated[str, Form()],
) -> RedirectResponse:
    """Update a forecast."""
    await update_forecast(
        account_id=account_id,
        forecast_id=forecast_id,
        name=name,
    )
    messages.success(f"Forecast '{name}' updated successfully!")
    return RedirectResponse(
        url="/settings/forecasts/", status_code=status.HTTP_303_SEE_OTHER
    )


#################
# Zone Settings #
#################


@router.get("/zones/", response_class=HTMLResponse)
async def zones_list(
    request: Request,
    account_id: CurrentAccount,
) -> Response:
    """List and manage zones."""
    zones = await get_all_zones(account_id=account_id)

    context = {
        "zones": zones,
        "active_tab": "zones",
    }
    return templates.TemplateResponse(request, "settings/zones.html", context)


@router.get("/zones/new/", response_class=HTMLResponse)
async def zone_new(
    request: Request,
    account_id: CurrentAccount,
) -> Response:
    """Form to add a new zone."""
    locations = await get_locations(account_id=account_id)

    context = {
        "locations": locations,
        "active_tab": "zones",
    }
    return templates.TemplateResponse(request, "settings/zone_form.html", context)


@router.post("/zones/new/", response_class=RedirectResponse)
async def zone_create(
    request: Request,
    account_id: CurrentAccount,
    messages: Messages,
    name: Annotated[str, Form()],
    location_id: Annotated[int, Form()],
    is_outdoor: Annotated[str | None, Form()] = None,
    color: Annotated[str | None, Form()] = None,
) -> RedirectResponse:
    """Create a new zone."""
    zone_id = await create_zone(
        account_id=account_id,
        location_id=location_id,
        name=name,
        is_outdoor=is_outdoor == "true",
        color=color or None,
    )
    if zone_id:
        messages.success(f"Zone '{name}' created successfully!")
    else:
        messages.error("Failed to create zone. Check that the location exists.")
    return RedirectResponse(
        url="/settings/zones/", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/zones/{zone_id}/", response_class=HTMLResponse)
async def zone_detail(
    request: Request,
    account_id: CurrentAccount,
    zone_id: Annotated[int, Path()],
) -> Response:
    """View zone details."""
    zone_data = await get_zone(account_id=account_id, zone_id=zone_id)
    if zone_data is None:
        raise HTTPException(status_code=404, detail="Zone not found")

    zone = {
        "id": zone_data[0],
        "name": zone_data[1],
        "location_id": zone_data[2],
        "location_name": zone_data[3],
        "is_outdoor": zone_data[4],
        "color": zone_data[5],
    }

    # Get assignment history
    assignments = await get_zone_assignments(account_id=account_id, zone_id=zone_id)

    # Find current assignment (if any)
    current_assignment = None
    for assignment_id, sensor_id, sensor_name, start_time, end_time in assignments:
        if end_time is None:
            current_assignment = {
                "id": assignment_id,
                "sensor_id": sensor_id,
                "sensor_name": sensor_name,
                "start_time": start_time,
            }
            break

    # Get available sensors for assignment
    all_sensors = await get_all_sensors(account_id=account_id)
    available_sensors = []
    for sensor_id, name, _location, _source in all_sensors:
        current_zone = await get_sensor_current_zone(
            account_id=account_id, sensor_id=sensor_id
        )
        available_sensors.append(
            {
                "id": sensor_id,
                "name": name,
                "current_zone": current_zone[1] if current_zone else None,
            }
        )

    context = {
        "zone": zone,
        "assignments": assignments,
        "current_assignment": current_assignment,
        "available_sensors": available_sensors,
        "active_tab": "zones",
    }
    return templates.TemplateResponse(request, "settings/zone_detail.html", context)


@router.post("/zones/{zone_id}/", response_class=RedirectResponse)
async def zone_update_view(
    request: Request,
    account_id: CurrentAccount,
    messages: Messages,
    zone_id: Annotated[int, Path()],
    name: Annotated[str, Form()],
    is_outdoor: Annotated[str | None, Form()] = None,
    color: Annotated[str | None, Form()] = None,
) -> RedirectResponse:
    """Update a zone."""
    await update_zone(
        account_id=account_id,
        zone_id=zone_id,
        name=name,
        is_outdoor=is_outdoor == "true",
        color=color,
    )
    messages.success(f"Zone '{name}' updated successfully!")
    return RedirectResponse(
        url="/settings/zones/", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/zones/{zone_id}/assign/", response_class=RedirectResponse)
async def zone_assign_sensor(
    request: Request,
    account_id: CurrentAccount,
    messages: Messages,
    zone_id: Annotated[int, Path()],
    sensor_id: Annotated[int, Form()],
) -> RedirectResponse:
    """Assign a sensor to a zone."""
    success = await assign_sensor_to_zone(
        account_id=account_id,
        zone_id=zone_id,
        sensor_id=sensor_id,
    )
    if success:
        messages.success("Sensor assigned successfully!")
    else:
        messages.error(
            "Failed to assign sensor. Check that both zone and sensor exist."
        )
    return RedirectResponse(
        url=f"/settings/zones/{zone_id}/", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/zones/{zone_id}/unassign/", response_class=RedirectResponse)
async def zone_unassign_sensor(
    request: Request,
    account_id: CurrentAccount,
    messages: Messages,
    zone_id: Annotated[int, Path()],
) -> RedirectResponse:
    """Unassign the current sensor from a zone."""
    # Get current assignment to find the sensor
    assignments = await get_zone_assignments(account_id=account_id, zone_id=zone_id)
    for _, sensor_id, _, _, end_time in assignments:
        if end_time is None:
            success = await unassign_sensor(account_id=account_id, sensor_id=sensor_id)
            if success:
                messages.success("Sensor unassigned successfully!")
            else:
                messages.error("Failed to unassign sensor.")
            break
    return RedirectResponse(
        url=f"/settings/zones/{zone_id}/", status_code=status.HTTP_303_SEE_OTHER
    )
