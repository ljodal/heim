from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from ..utils import timed
from .queries import get_account
from .utils import compare_password

basic_auth = HTTPBasic()


async def current_account(
    credentials: HTTPBasicCredentials = Depends(basic_auth),
) -> int:

    with timed("Check credentials"):
        if account := await get_account(username=credentials.username):
            account_id, password = account

            if compare_password(
                stored_password=password, provided_password=credentials.password
            ):
                return account_id

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password",
        headers={"WWW-Authenticate": "Basic"},
    )
