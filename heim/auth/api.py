from typing import Annotated
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm

from ..accounts.queries import get_account
from ..accounts.utils import compare_password
from .models import TokenResponse
from .queries import create_session

router = APIRouter(prefix="/auth")


@router.get("/authorize")
async def authorize(
    redirect_uri: Annotated[str, Query()],
) -> RedirectResponse:
    """
    OAuth2 authorize endpoint for native apps.

    Redirects to login page, which will redirect back to the app with the token.
    Only allows custom URL schemes (not http/https) to prevent open redirects.
    """
    parsed = urlparse(redirect_uri)
    if parsed.scheme in ("http", "https", ""):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="redirect_uri must use a custom URL scheme",
        )

    return RedirectResponse(
        url=f"/login/?redirect_uri={redirect_uri}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/token", response_model=TokenResponse)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> TokenResponse:
    account = await get_account(username=form_data.username)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect username or password",
        )

    account_id, password = account
    if not compare_password(
        stored_password=password, provided_password=form_data.password
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect username or password",
        )

    session = await create_session(account_id=account_id)

    return TokenResponse(access_token=session.key, token_type="bearer")
