from datetime import datetime, timedelta, timezone

import pytest

from weather_station.accounts.utils import get_random_string
from weather_station.integrations.aqara.queries import create_aqara_account

pytestmark = pytest.mark.asyncio


async def test_create_aqara_account(connection, account_id: int, username: str) -> None:

    aqara_account_id = await create_aqara_account(
        account_id=account_id,
        username=username,
        access_token=get_random_string(10),
        refresh_token=get_random_string(10),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    assert aqara_account_id > 0
