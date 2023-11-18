from typing import Annotated

from fastapi import Depends, HTTPException, status

from ..auth.dependencies import CookieSession
from .messages import Messages


async def get_current_account(session: CookieSession, messages: Messages) -> int:
    if session is None:
        messages.notice("Login required")
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )

    return session.account_id


CurrentAccount = Annotated[int, Depends(get_current_account)]
