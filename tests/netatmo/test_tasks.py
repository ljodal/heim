from datetime import UTC, datetime, timedelta

import pytest
from heim import db
from heim.integrations.netatmo.client import NetatmoClient
from heim.integrations.netatmo.queries import get_netatmo_sensor
from heim.integrations.netatmo.tasks import update_sensor_data
from pytest_mock import MockerFixture

pytestmark = pytest.mark.asyncio


async def test_update_sensor_data(
    sensor_id: int,
    account_id: int,
    netatmo_module_id: str,
    netatmo_station_id: str,
    module_type: str,
    measure_types: list[str],
    mocker: MockerFixture,
) -> None:
    now = datetime.now(UTC)

    # Mock the get_measure response
    mock_measurements: dict[str, list[tuple[datetime, float | None]]] = {
        "Temperature": [
            (now, 21.5),
            (now + timedelta(hours=1), 22.0),
        ],
        "Humidity": [
            (now, 45.0),
            (now + timedelta(hours=1), 48.0),
        ],
        "CO2": [
            (now, 800.0),
            (now + timedelta(hours=1), 750.0),
        ],
        "Noise": [
            (now, 35.0),
            (now + timedelta(hours=1), 32.0),
        ],
        "Pressure": [
            (now, 1013.25),
            (now + timedelta(hours=1), 1014.0),
        ],
    }

    mocker.patch.object(NetatmoClient, "get_measure", return_value=mock_measurements)

    await update_sensor_data(account_id=account_id, sensor_id=sensor_id)

    netatmo_id, station_id, mtype, last_update_time = await get_netatmo_sensor(
        account_id=account_id, sensor_id=sensor_id
    )
    assert netatmo_id == netatmo_module_id
    assert mtype == module_type
    assert last_update_time == now + timedelta(hours=1)

    # Should have 10 measurements (2 timestamps x 5 measure types)
    count = await db.fetchval(
        "SELECT COUNT(*) FROM sensor_measurement WHERE sensor_id = $1", sensor_id
    )
    assert count == 10


async def test_update_sensor_data_no_data(
    sensor_id: int,
    account_id: int,
    mocker: MockerFixture,
) -> None:
    # Mock empty response
    mock_measurements: dict[str, list[tuple[datetime, float | None]]] = {
        "Temperature": [],
        "Humidity": [],
    }

    mocker.patch.object(NetatmoClient, "get_measure", return_value=mock_measurements)

    await update_sensor_data(account_id=account_id, sensor_id=sensor_id)

    # Should have no measurements
    count = await db.fetchval(
        "SELECT COUNT(*) FROM sensor_measurement WHERE sensor_id = $1", sensor_id
    )
    assert count == 0


async def test_update_sensor_data_with_none_values(
    sensor_id: int,
    account_id: int,
    mocker: MockerFixture,
) -> None:
    now = datetime.now(UTC)

    # Mock response with some None values (sensor offline, etc.)
    mock_measurements: dict[str, list[tuple[datetime, float | None]]] = {
        "Temperature": [
            (now, 21.5),
            (now + timedelta(hours=1), None),  # Missing value
        ],
        "Humidity": [
            (now, None),  # Missing value
            (now + timedelta(hours=1), 48.0),
        ],
    }

    mocker.patch.object(NetatmoClient, "get_measure", return_value=mock_measurements)

    await update_sensor_data(account_id=account_id, sensor_id=sensor_id)

    # Should only have 2 measurements (None values are skipped)
    count = await db.fetchval(
        "SELECT COUNT(*) FROM sensor_measurement WHERE sensor_id = $1", sensor_id
    )
    assert count == 2
