"""
Fixtures for local forecast tests.
"""

from datetime import datetime, timedelta, timezone

import pytest

from heim import db
from heim.forecasts.queries import create_forecast, create_forecast_instance
from heim.sensors.queries import save_measurements
from heim.sensors.types import Attribute


@pytest.fixture
async def sensor_id(connection: None, account_id: int, location_id: int) -> int:
    """Create a basic sensor (without Aqara integration)."""
    return await db.fetchval(  # type: ignore[no-any-return]
        """
        INSERT INTO sensor (account_id, location_id, name)
        VALUES ($1, $2, $3)
        RETURNING id
        """,
        account_id,
        location_id,
        "Test sensor",
    )


@pytest.fixture
async def forecast_id(connection: None, account_id: int, location_id: int) -> int:
    """Create a forecast for the test location."""
    return await create_forecast(
        name="Test forecast",
        account_id=account_id,
        location_id=location_id,
    )


@pytest.fixture
def base_time() -> datetime:
    """Base time for test data."""
    return datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
async def forecast_with_values(
    connection: None,
    forecast_id: int,
    base_time: datetime,
) -> int:
    """
    Create a forecast instance with values.

    Creates forecast values for the next 48 hours.
    Temperature values are in 100x scale (e.g., 500 = 5.0°C).
    """
    values = [
        # (attribute, measured_at, value)
        (Attribute.AIR_TEMPERATURE, base_time + timedelta(hours=h), 500 + h * 10)
        for h in range(48)
    ]

    await create_forecast_instance(
        forecast_id=forecast_id,
        forecast_time=base_time,
        values=values,
    )

    return forecast_id


@pytest.fixture
async def sensor_with_measurements(
    connection: None,
    sensor_id: int,
    base_time: datetime,
) -> int:
    """
    Create sensor measurements.

    Creates measurements for the next 48 hours.
    Temperature values are in 100x scale, slightly different from forecast
    to simulate real-world bias.
    """
    # Simulate bias: sensor reads 50 (0.5°C) lower than forecast
    values = [
        (Attribute.AIR_TEMPERATURE, base_time + timedelta(hours=h), 450 + h * 10)
        for h in range(48)
    ]

    await save_measurements(sensor_id=sensor_id, values=values)

    return sensor_id
