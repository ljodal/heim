from datetime import datetime

from pydantic import BaseModel


class NetatmoAccount(BaseModel):
    id: int
    account_id: int
    access_token: str
    refresh_token: str
    expires_at: datetime
