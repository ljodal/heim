from fastapi import Cookie, Depends
from fastapi.exceptions import HTTPException
from starlette.status import HTTP_401_UNAUTHORIZED

from . import queries
from .models import Session


async def get_session(session_id: str = Cookie(None)) -> Session | None:
    return await queries.get_session(key=session_id) if session_id else None


async def require_login(
    session: Session | None = Depends(get_session),
) -> int | None:
    if session is None:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Login required",
        )

    return session.account_id
