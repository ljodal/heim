from datetime import UTC, datetime, timedelta

import pytest
from heim.accounts.utils import get_random_string
from heim.integrations.netatmo.queries import (
    create_netatmo_account,
    create_netatmo_sensor,
)
from heim.integrations.netatmo.tasks import MODULE_TYPE_ATTRIBUTES


@pytest.fixture
async def netatmo_account_id(connection: None, account_id: int) -> int:
    return await create_netatmo_account(
        account_id=account_id,
        access_token=get_random_string(10),
        refresh_token=get_random_string(10),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


@pytest.fixture
def module_type() -> str:
    return "NAMain"


@pytest.fixture
def netatmo_module_id() -> str:
    return "70:ee:50:" + get_random_string(8)


@pytest.fixture
def netatmo_station_id(netatmo_module_id: str) -> str:
    # For NAMain, station_id equals module_id
    return netatmo_module_id


@pytest.fixture
async def sensor_id(
    connection: None,
    account_id: int,
    netatmo_account_id: int,
    location_id: int,
    module_type: str,
    netatmo_module_id: str,
    netatmo_station_id: str,
) -> int:
    return await create_netatmo_sensor(
        account_id=account_id,
        location_id=location_id,
        name="Test sensor",
        module_type=module_type,
        netatmo_id=netatmo_module_id,
        station_id=netatmo_station_id,
    )


@pytest.fixture
def measure_types(module_type: str) -> list[str]:
    return list(MODULE_TYPE_ATTRIBUTES.get(module_type, {}).keys())
