from datetime import datetime, timedelta, timezone

import pytest

from weather_station.accounts.utils import get_random_string
from weather_station.integrations.aqara.queries import (
    create_aqara_account,
    create_aqara_sensor,
)
from weather_station.integrations.aqara.tasks import MODEL_TO_RESOURCE_MAPPING


@pytest.fixture
async def aqara_account_id(connection, account_id: int, username: str) -> int:
    return await create_aqara_account(
        account_id=account_id,
        username=username,
        access_token=get_random_string(10),
        refresh_token=get_random_string(10),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )


@pytest.fixture
def sensor_model() -> str:
    return next(iter(MODEL_TO_RESOURCE_MAPPING))


@pytest.fixture
def resource_id(sensor_model: str) -> str:
    return next(iter(MODEL_TO_RESOURCE_MAPPING[sensor_model]))


@pytest.fixture
def aqara_sensor_id() -> str:
    return get_random_string(3)


@pytest.fixture
async def sensor_id(
    connection,
    account_id: int,
    aqara_account_id: int,
    location_id: int,
    sensor_model: str,
    aqara_sensor_id: str,
) -> int:
    return await create_aqara_sensor(
        account_id=account_id,
        location_id=location_id,
        name="Test sensor",
        model=sensor_model,
        aqara_id=aqara_sensor_id,
    )
