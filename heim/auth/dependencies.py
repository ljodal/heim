from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from .models import Session
from .queries import get_session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


async def get_current_session(
    session_key: Optional[str] = Depends(oauth2_scheme),
) -> Optional[Session]:
    return await get_session(key=session_key) if session_key else None


async def current_account(
    session: Optional[Session] = Depends(get_current_session),
) -> int:
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return session.account_id
