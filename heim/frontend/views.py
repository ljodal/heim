from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Path, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..accounts.queries import get_account, get_locations
from ..accounts.utils import compare_password, hash_password
from ..api.selectors import get_temperature_chart_data
from ..auth.dependencies import CookieSession
from ..auth.queries import create_session, delete_session
from ..forecasts.queries import get_latest_forecast_values
from ..sensors.queries import get_measurements_averaged, get_sensors
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
def login(request: Request, redirect_uri: str | None = None) -> Response:
    """
    Render the login form. The actual login is handled by the view below.

    If redirect_uri is provided (from /api/auth/authorize), it will be passed
    to the template and included as a hidden form field.
    """
    return templates.TemplateResponse(
        request, "login.html", {"redirect_uri": redirect_uri}
    )


@router.post("/login/", response_class=RedirectResponse)
async def do_login(
    request: Request,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    messages: Messages,
    redirect_uri: Annotated[str | None, Form()] = None,
) -> RedirectResponse:
    """
    Authenticate the user and set a session cookie.

    If redirect_uri is provided (OAuth2 flow for native apps), redirects to
    the app callback with the access token in the URL fragment.
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
        # Preserve redirect_uri on failed login
        login_url = "/login/"
        if redirect_uri:
            login_url = f"/login/?redirect_uri={redirect_uri}"
        return RedirectResponse(url=login_url, status_code=status.HTTP_303_SEE_OTHER)

    session = await create_session(account_id=account_id)

    # OAuth2 flow: redirect to app with token in fragment
    if redirect_uri:
        return RedirectResponse(
            url=f"{redirect_uri}#access_token={session.key}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # Normal web flow: set cookie and redirect to home
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
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

    # Get indoor sensor data for charts (averaged over 1-hour buckets)
    sensors = await get_sensors(
        account_id=account_id, location_id=location_id, is_outdoor=False
    )
    sensor_data = []
    for sensor_id, sensor_name, sensor_color in sensors:
        measurements = await get_measurements_averaged(
            sensor_id=sensor_id,
            attribute=Attribute.AIR_TEMPERATURE,
            hours=168,
            bucket_minutes=60,
        )
        if measurements:
            sensor_data.append(
                {
                    "id": sensor_id,
                    "name": sensor_name or f"Sensor {sensor_id}",
                    "color": sensor_color,
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
    chart_data = await get_temperature_chart_data(
        account_id=account_id, location_id=location_id
    )
    if chart_data:
        outdoor_hub_data = {
            "measurements": {
                "labels": [r.date.isoformat() for r in chart_data.history],
                "values": [r.temperature for r in chart_data.history],
            },
            "forecasts": [
                {
                    "created_at": f.created_at.isoformat(),
                    "age_hours": f.age_hours,
                    "labels": [r.date.isoformat() for r in f.data],
                    "values": [r.temperature for r in f.data],
                }
                for f in chart_data.forecasts
            ],
            "now": chart_data.now.isoformat(),
        }

    context = {
        "locations": locations,
        "current_location": current_location,
        "sensor_data": sensor_data,
        "forecast_data": forecast_data,
        "outdoor_hub_data": outdoor_hub_data,
    }
    return templates.TemplateResponse(request, "index.html", context)
