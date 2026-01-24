from datetime import UTC, datetime, timedelta

import pytest
from heim import db
from heim.accounts.utils import get_random_string
from heim.integrations.aqara.queries import (
    create_aqara_account,
    create_aqara_sensor,
    get_aqara_sensor,
)

pytestmark = pytest.mark.asyncio


async def test_create_aqara_account(
    connection: None, account_id: int, username: str
) -> None:
    aqara_account_id = await create_aqara_account(
        account_id=account_id,
        username=username,
        access_token=get_random_string(10),
        refresh_token=get_random_string(10),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    assert aqara_account_id > 0


async def test_create_aqara_sensor(
    connection: None,
    account_id: int,
    aqara_account_id: int,
    location_id: int,
    sensor_model: str,
    aqara_sensor_id: str,
) -> None:
    await create_aqara_sensor(
        account_id=account_id,
        location_id=location_id,
        name="Test sensor",
        model=sensor_model,
        aqara_id=aqara_sensor_id,
    )
    assert await db.fetchval("SELECT count(*) FROM aqara_sensor") == 1


async def test_get_aqara_sensor(
    connection: None, account_id: int, aqara_sensor_id: int, sensor_id: int
) -> None:
    aqara_id, model, last_update_time = await get_aqara_sensor(
        account_id=account_id, sensor_id=sensor_id
    )
