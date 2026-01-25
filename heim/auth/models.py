from datetime import datetime
from typing import Any, Literal

import pydantic


class TokenResponse(pydantic.BaseModel):
    access_token: str
    token_type: Literal["bearer"]


class Session(pydantic.BaseModel):
    key: str
    account_id: int
    data: dict[str, Any]
    expires_at: datetime
