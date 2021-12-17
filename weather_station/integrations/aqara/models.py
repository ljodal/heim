from datetime import datetime

from pydantic import BaseModel


class AqaraAccount(BaseModel):
    id: int
    account_id: int
    username: str
    access_token: str
    refresh_token: str
    expire_at: datetime
