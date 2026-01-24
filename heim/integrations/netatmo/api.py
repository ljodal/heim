from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .client import NetatmoClient
from .exceptions import InvalidGrant, NetatmoAPIError
from .queries import create_netatmo_account

router = APIRouter(prefix="/netatmo", tags=["netatmo"])
templates = Jinja2Templates(directory="heim/frontend/templates")
templates.env.loader.searchpath.append("heim/integrations/netatmo/templates")


@router.get("/callback", response_class=HTMLResponse)
async def oauth_callback(
    request: Request,
    code: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    state: str | None = None,
) -> HTMLResponse:
    """
    OAuth callback endpoint for Netatmo authorization.

    Exchanges the authorization code for tokens and saves the account.
    The state parameter contains the account_id to link to.
    """
    # Parse account_id from state parameter
    try:
        account_id = int(state) if state else 1
    except ValueError:
        account_id = 1

    if error:
        return templates.TemplateResponse(
            "callback.html",
            {
                "request": request,
                "success": False,
                "error": error,
                "error_description": error_description,
            },
        )

    if not code:
        return templates.TemplateResponse(
            "callback.html",
            {
                "request": request,
                "success": False,
                "error": "missing_code",
                "error_description": "No authorization code was provided.",
            },
        )

    # Build the redirect URI (must match what was used in the auth request)
    redirect_uri = str(request.url_for("oauth_callback"))

    try:
        async with NetatmoClient() as client:
            result = await client.get_token_from_code(
                code=code, redirect_uri=redirect_uri
            )

        await create_netatmo_account(
            account_id=account_id,
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            expires_at=datetime.now(UTC) + timedelta(seconds=result.expires_in),
        )

        return templates.TemplateResponse(
            "callback.html",
            {
                "request": request,
                "success": True,
                "account_id": account_id,
            },
        )

    except InvalidGrant as e:
        return templates.TemplateResponse(
            "callback.html",
            {
                "request": request,
                "success": False,
                "error": "invalid_grant",
                "error_description": str(e),
            },
        )

    except NetatmoAPIError as e:
        return templates.TemplateResponse(
            "callback.html",
            {
                "request": request,
                "success": False,
                "error": "api_error",
                "error_description": str(e),
            },
        )

    except Exception as e:
        return templates.TemplateResponse(
            "callback.html",
            {
                "request": request,
                "success": False,
                "error": "unexpected_error",
                "error_description": str(e),
            },
        )
