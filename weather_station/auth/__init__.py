from typing import Optional

from fastapi import Cookie, Depends
from fastapi.exceptions import HTTPException
from starlette.status import HTTP_401_UNAUTHORIZED

from . import queries
from .models import Session


async def get_session(session_id: str = Cookie(None)) -> Optional[Session]:
    return await queries.get_session(session_key=session_id) if session_id else None


async def require_login(
    session: Optional[Session] = Depends(get_session),
) -> Optional[int]:
    if session is None:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Login required",
        )

    return session.account_id
