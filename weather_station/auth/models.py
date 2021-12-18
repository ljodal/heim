from typing import Any

import pydantic


class Session(pydantic.BaseModel):
    key: str
    account_id: int
    data: dict[str, Any]
