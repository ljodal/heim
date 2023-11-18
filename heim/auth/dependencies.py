from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from .models import Session
from .queries import get_session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


async def get_cookie_session(request: Request) -> Session | None:
    session_key = request.cookies.get("session_id")
    return await get_session(key=session_key) if session_key else None


CookieSession = Annotated[Session | None, Depends(get_cookie_session)]


async def get_oauth_session(
    session_key: str | None = Depends(oauth2_scheme),
) -> Session | None:
    return await get_session(key=session_key) if session_key else None


OAuthSession = Annotated[Session | None, Depends(get_oauth_session)]


async def current_account(session: OAuthSession) -> int:
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return session.account_id
