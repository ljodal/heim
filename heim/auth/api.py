from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from ..accounts.queries import get_account
from ..accounts.utils import compare_password
from .models import TokenResponse
from .queries import create_session

router = APIRouter(prefix="/auth")


@router.post("/token", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
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
