from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Form, HTTPException, Path, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..accounts.queries import get_account, get_locations
from ..accounts.utils import compare_password, hash_password
from ..auth.dependencies import CookieSession
from ..auth.queries import create_session, delete_session
from ..forecasts.queries import get_forecast, get_instances, get_latest_forecast_values
from ..sensors.queries import get_measurements, get_outdoor_sensors, get_sensors
from ..sensors.types import Attribute
from .dependencies import CurrentAccount
from .messages import Messages, get_messages

router = APIRouter()
templates = Jinja2Templates(directory="heim/frontend/templates")
templates.env.globals["get_messages"] = get_messages
fallback_password = hash_password("foobar")


@router.get("/", response_class=RedirectResponse)
async def index(request: Request, account_id: CurrentAccount) -> RedirectResponse:
    locations = await get_locations(account_id=account_id)
    return RedirectResponse(
        url=f"/{locations[0].id}/", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/login/", response_class=HTMLResponse)
def login(request: Request) -> Response:
    """
    Render the login form. The actual login is handled by the view below
    """

    context: dict[str, Any] = {"request": request}
    return templates.TemplateResponse("login.html", context)


@router.post("/login/", response_class=RedirectResponse)
async def do_login(
    request: Request,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    messages: Messages,
) -> RedirectResponse:
    """
    Authenticate the user and set a session cookie.
    """

    if account := await get_account(username=username):
        account_id, stored_password = account
    else:
        account_id, stored_password = None, fallback_password

    if (
        not compare_password(
            stored_password=stored_password, provided_password=password
        )
        or account_id is None
    ):
        messages.error("Invalid credentials")
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    session = await create_session(account_id=account_id)
    response.set_cookie("session_id", session.key)
    return response


@router.get("/logout/", response_class=RedirectResponse)
async def logout(request: Request, session: CookieSession) -> RedirectResponse:
    if session:
        await delete_session(session)
    response = RedirectResponse(url="/login/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("session_id")
    return response


@router.get("/{location_id}/", response_class=HTMLResponse)
async def location_overview(
    request: Request,
    account_id: CurrentAccount,
    location_id: Annotated[int, Path(title="Location ID")],
) -> Response:
    locations = await get_locations(account_id=account_id)
    try:
        current_location = next(
            location for location in locations if location.id == location_id
        )
    except StopIteration as e:
        raise HTTPException(status_code=404, detail="Unknown location") from e

    # Get sensor data for charts
    sensors = await get_sensors(account_id=account_id, location_id=location_id)
    sensor_data = []
    for sensor_id, sensor_name in sensors:
        measurements = await get_measurements(
            sensor_id=sensor_id, attribute=Attribute.AIR_TEMPERATURE, hours=168
        )
        if measurements:
            sensor_data.append(
                {
                    "name": sensor_name or f"Sensor {sensor_id}",
                    "labels": [m[0].isoformat() for m in measurements],
                    "values": [m[1] / 100 for m in measurements],
                }
            )

    # Get forecast data
    forecast_values = await get_latest_forecast_values(
        location_id=location_id, attribute=Attribute.AIR_TEMPERATURE
    )
    forecast_data = None
    if forecast_values:
        forecast_data = {
            "labels": [v[0].isoformat() for v in forecast_values],
            "values": [v[1] / 100 for v in forecast_values],
        }

    # Build outdoor hub data
    outdoor_hub_data = None
    outdoor_sensors = await get_outdoor_sensors(
        account_id=account_id, location_id=location_id
    )
    if outdoor_sensors:
        now = datetime.now(UTC)

        # Collect measurements from all outdoor sensors (48h)
        all_measurements: list[tuple[datetime, float]] = []
        for sensor_id, _ in outdoor_sensors:
            measurements = await get_measurements(
                sensor_id=sensor_id, attribute=Attribute.AIR_TEMPERATURE, hours=48
            )
            all_measurements.extend(measurements)

        # Sort by time and convert values
        all_measurements.sort(key=lambda m: m[0])

        # Get forecast instances
        forecast_id = await get_forecast(account_id=account_id, location_id=location_id)
        forecasts: list[dict[str, Any]] = []
        if forecast_id:
            instances = await get_instances(
                forecast_id=forecast_id, attribute=Attribute.AIR_TEMPERATURE
            )
            for created_at, values in instances.items():
                age_hours = (now - created_at).total_seconds() / 3600
                # Filter to future values only
                future_values = [(ts, val) for ts, val in values if ts > now]
                if future_values:
                    forecasts.append(
                        {
                            "created_at": created_at.isoformat(),
                            "age_hours": age_hours,
                            "labels": [v[0].isoformat() for v in future_values],
                            "values": [v[1] / 100 for v in future_values],
                        }
                    )

        outdoor_hub_data = {
            "measurements": {
                "labels": [m[0].isoformat() for m in all_measurements],
                "values": [m[1] / 100 for m in all_measurements],
            },
            "forecasts": forecasts,
            "now": now.isoformat(),
        }

    context = {
        "request": request,
        "locations": locations,
        "current_location": current_location,
        "sensor_data": sensor_data,
        "forecast_data": forecast_data,
        "outdoor_hub_data": outdoor_hub_data,
    }
    return templates.TemplateResponse("index.html", context)
