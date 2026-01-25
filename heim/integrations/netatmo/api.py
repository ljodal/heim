from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from ...frontend.messages import Messages
from .client import NetatmoClient
from .exceptions import InvalidGrant, NetatmoAPIError
from .queries import create_netatmo_account

router = APIRouter(prefix="/netatmo", tags=["netatmo"])

REDIRECT_URL = "/settings/netatmo/"


@router.get("/callback")
async def oauth_callback(
    request: Request,
    messages: Messages,
    code: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    state: str | None = None,
) -> RedirectResponse:
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
        msg = f"Authorization failed: {error}"
        if error_description:
            msg += f" - {error_description}"
        messages.error(msg)
        return RedirectResponse(url=REDIRECT_URL, status_code=303)

    if not code:
        messages.error("Authorization failed: No authorization code was provided.")
        return RedirectResponse(url=REDIRECT_URL, status_code=303)

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

        messages.success(
            "Netatmo account linked successfully! You can now add sensors."
        )

    except InvalidGrant as e:
        messages.error(f"Authorization failed: {e}")

    except NetatmoAPIError as e:
        messages.error(f"Netatmo API error: {e}")

    except Exception as e:
        messages.error(f"Unexpected error: {e}")

    return RedirectResponse(url=REDIRECT_URL, status_code=303)
