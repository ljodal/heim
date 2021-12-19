from datetime import datetime

from pydantic import BaseModel


class AqaraAccount(BaseModel):
    id: int
    account_id: int
    username: str
    access_token: str
    refresh_token: str
    expires_at: datetime
