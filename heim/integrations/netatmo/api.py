from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from pydantic import TypeAdapter

from ...frontend.messages import Message
from .client import NetatmoClient
from .exceptions import InvalidGrant, NetatmoAPIError
from .queries import create_netatmo_account

router = APIRouter(prefix="/netatmo", tags=["netatmo"])

# For encoding flash messages in cookies
_message_adapter = TypeAdapter(list[Message])


def _redirect_with_message(url: str, level: str, message: str) -> RedirectResponse:
    """Create a redirect response with a flash message cookie."""
    response = RedirectResponse(url=url, status_code=303)
    messages = [Message(level=level, message=message)]  # type: ignore[arg-type]
    response.set_cookie("messages", _message_adapter.dump_json(messages).decode())
    return response


@router.get("/callback")
async def oauth_callback(
    request: Request,
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
        return _redirect_with_message("/settings/netatmo/", "error", msg)

    if not code:
        return _redirect_with_message(
            "/settings/netatmo/",
            "error",
            "Authorization failed: No authorization code was provided.",
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

        return _redirect_with_message(
            "/settings/netatmo/",
            "success",
            "Netatmo account linked successfully! You can now add sensors.",
        )

    except InvalidGrant as e:
        return _redirect_with_message(
            "/settings/netatmo/",
            "error",
            f"Authorization failed: {e}",
        )

    except NetatmoAPIError as e:
        return _redirect_with_message(
            "/settings/netatmo/",
            "error",
            f"Netatmo API error: {e}",
        )

    except Exception as e:
        return _redirect_with_message(
            "/settings/netatmo/",
            "error",
            f"Unexpected error: {e}",
        )
