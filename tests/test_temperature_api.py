from datetime import UTC, datetime, timedelta

import httpx
import pytest
from heim import db
from heim.sensors.queries import save_measurements
from heim.sensors.types import Attribute

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def outdoor_sensor_id(connection: None, account_id: int, location_id: int) -> int:
    """Create an outdoor sensor."""
    sensor_id: int = await db.fetchval(
        """
        INSERT INTO sensor (account_id, location_id, name, is_outdoor, color)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id
        """,
        account_id,
        location_id,
        "Outside",
        True,
        "#FF6B6B",
    )
    return sensor_id


@pytest.fixture
async def indoor_sensor_id(connection: None, account_id: int, location_id: int) -> int:
    """Create an indoor sensor."""
    sensor_id: int = await db.fetchval(
        """
        INSERT INTO sensor (account_id, location_id, name, is_outdoor, color)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id
        """,
        account_id,
        location_id,
        "Living Room",
        False,
        "#4ECDC4",
    )
    return sensor_id


@pytest.fixture
async def outdoor_sensor_with_measurements(outdoor_sensor_id: int) -> int:
    """Create an outdoor sensor with measurements for the last 48 hours."""
    now = datetime.now(UTC)
    measurements = [
        (Attribute.AIR_TEMPERATURE, now - timedelta(hours=i), -500 + i * 10)
        for i in range(48)
    ]
    await save_measurements(sensor_id=outdoor_sensor_id, values=measurements)
    return outdoor_sensor_id


@pytest.fixture
async def indoor_sensor_with_measurements(indoor_sensor_id: int) -> int:
    """Create an indoor sensor with measurements for the last 48 hours."""
    now = datetime.now(UTC)
    measurements = [
        (Attribute.AIR_TEMPERATURE, now - timedelta(hours=i), 2100 + i * 5)
        for i in range(48)
    ]
    await save_measurements(sensor_id=indoor_sensor_id, values=measurements)
    return indoor_sensor_id


# Temperature Chart API Tests


async def test_temperature_chart_returns_data(
    authenticated_client: httpx.AsyncClient,
    location_id: int,
    outdoor_sensor_with_measurements: int,
) -> None:
    response = await authenticated_client.get(
        f"/api/locations/{location_id}/temperature-chart"
    )
    assert response.status_code == 200

    data = response.json()
    assert "location_name" in data
    assert "current_temperature" in data
    assert "last_updated" in data
    assert "history" in data
    assert "forecasts" in data
    assert "now" in data

    assert isinstance(data["history"], list)
    assert len(data["history"]) > 0

    reading = data["history"][0]
    assert "date" in reading
    assert "temperature" in reading


async def test_temperature_chart_unauthenticated(
    client: httpx.AsyncClient,
    location_id: int,
    outdoor_sensor_with_measurements: int,
) -> None:
    response = await client.get(f"/api/locations/{location_id}/temperature-chart")
    assert response.status_code == 401


async def test_temperature_chart_no_outdoor_sensor(
    authenticated_client: httpx.AsyncClient,
    location_id: int,
) -> None:
    response = await authenticated_client.get(
        f"/api/locations/{location_id}/temperature-chart"
    )
    assert response.status_code == 404


async def test_temperature_chart_nonexistent_location(
    authenticated_client: httpx.AsyncClient,
) -> None:
    response = await authenticated_client.get("/api/locations/99999/temperature-chart")
    assert response.status_code == 404


# Temperature History API Tests


async def test_temperature_history_returns_data(
    authenticated_client: httpx.AsyncClient,
    location_id: int,
    outdoor_sensor_with_measurements: int,
    indoor_sensor_with_measurements: int,
) -> None:
    response = await authenticated_client.get(
        f"/api/locations/{location_id}/temperature-history"
    )
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2

    # Check structure of sensor data
    sensor = data[0]
    assert "sensor_name" in sensor
    assert "is_outdoor" in sensor
    assert "color" in sensor
    assert "readings" in sensor

    assert isinstance(sensor["readings"], list)
    assert len(sensor["readings"]) > 0

    reading = sensor["readings"][0]
    assert "date" in reading
    assert "temperature" in reading


async def test_temperature_history_with_days_param(
    authenticated_client: httpx.AsyncClient,
    location_id: int,
    outdoor_sensor_with_measurements: int,
) -> None:
    response = await authenticated_client.get(
        f"/api/locations/{location_id}/temperature-history?days=1"
    )
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1

    # With 1 day of data, should have fewer readings than default 7 days
    sensor = data[0]
    assert len(sensor["readings"]) <= 24  # At most 24 hours of 15-min buckets


async def test_temperature_history_unauthenticated(
    client: httpx.AsyncClient,
    location_id: int,
    outdoor_sensor_with_measurements: int,
) -> None:
    response = await client.get(f"/api/locations/{location_id}/temperature-history")
    assert response.status_code == 401


async def test_temperature_history_empty_location(
    authenticated_client: httpx.AsyncClient,
    location_id: int,
) -> None:
    """Location with no sensors should return empty list."""
    response = await authenticated_client.get(
        f"/api/locations/{location_id}/temperature-history"
    )
    assert response.status_code == 200
    assert response.json() == []


async def test_temperature_history_invalid_days_param(
    authenticated_client: httpx.AsyncClient,
    location_id: int,
) -> None:
    response = await authenticated_client.get(
        f"/api/locations/{location_id}/temperature-history?days=0"
    )
    assert response.status_code == 422

    response = await authenticated_client.get(
        f"/api/locations/{location_id}/temperature-history?days=400"
    )
    assert response.status_code == 422
