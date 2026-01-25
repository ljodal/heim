from datetime import UTC, datetime, timedelta

import pytest
from heim import db
from heim.accounts.utils import get_random_string
from heim.integrations.netatmo.queries import (
    create_netatmo_account,
    create_netatmo_sensor,
    get_netatmo_account,
    get_netatmo_sensor,
    get_netatmo_sensors,
)

pytestmark = pytest.mark.asyncio


async def test_create_netatmo_account(connection: None, account_id: int) -> None:
    netatmo_account_id = await create_netatmo_account(
        account_id=account_id,
        access_token=get_random_string(10),
        refresh_token=get_random_string(10),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    assert netatmo_account_id > 0


async def test_get_netatmo_account(
    connection: None, account_id: int, netatmo_account_id: int
) -> None:
    account = await get_netatmo_account(account_id=account_id)
    assert account.id == netatmo_account_id
    assert account.account_id == account_id


async def test_create_netatmo_sensor(
    connection: None,
    account_id: int,
    netatmo_account_id: int,
    location_id: int,
    module_type: str,
    netatmo_module_id: str,
    netatmo_station_id: str,
) -> None:
    await create_netatmo_sensor(
        account_id=account_id,
        location_id=location_id,
        name="Test sensor",
        module_type=module_type,
        netatmo_id=netatmo_module_id,
        station_id=netatmo_station_id,
    )
    assert await db.fetchval("SELECT count(*) FROM netatmo_sensor") == 1


async def test_get_netatmo_sensors(
    connection: None,
    account_id: int,
    sensor_id: int,
    module_type: str,
) -> None:
    sensors = await get_netatmo_sensors(account_id=account_id)
    assert len(sensors) == 1
    sid, name, mtype = sensors[0]
    assert sid == sensor_id
    assert name == "Test sensor"
    assert mtype == module_type


async def test_get_netatmo_sensor(
    connection: None,
    account_id: int,
    sensor_id: int,
    netatmo_module_id: str,
    netatmo_station_id: str,
    module_type: str,
) -> None:
    netatmo_id, station_id, mtype, last_update_time = await get_netatmo_sensor(
        account_id=account_id, sensor_id=sensor_id
    )
    assert netatmo_id == netatmo_module_id
    assert station_id == netatmo_station_id
    assert mtype == module_type
    assert last_update_time is None  # No measurements yet
