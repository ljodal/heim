"""
Tests for local forecast database queries.
"""

from datetime import datetime, timedelta, timezone

import pytest

from heim.local_forecast.queries import (
    get_bias_stats,
    get_forecast_and_sensor_for_location,
    get_latest_forecast_values,
    get_paired_observations,
    upsert_bias_stats,
)
from heim.local_forecast.stats import WelfordState
from heim.sensors.types import Attribute


@pytest.mark.asyncio
async def test_get_forecast_and_sensor_for_location(
    connection: None,
    account_id: int,
    location_id: int,
    forecast_id: int,
    sensor_id: int,
) -> None:
    result = await get_forecast_and_sensor_for_location(
        account_id=account_id,
        location_id=location_id,
    )

    assert result is not None
    assert result == (forecast_id, sensor_id)


@pytest.mark.asyncio
async def test_get_forecast_and_sensor_no_data(
    connection: None,
    account_id: int,
    location_id: int,
) -> None:
    result = await get_forecast_and_sensor_for_location(
        account_id=account_id,
        location_id=location_id,
    )

    assert result is None


@pytest.mark.asyncio
async def test_get_latest_forecast_values(
    connection: None,
    forecast_with_values: int,
    base_time: datetime,
) -> None:
    result = await get_latest_forecast_values(
        forecast_id=forecast_with_values,
        attribute=Attribute.AIR_TEMPERATURE,
    )

    assert result is not None
    created_at, values = result
    assert created_at == base_time
    assert len(values) == 48
    # Check first value
    assert values[0] == (base_time, 500)
    # Check last value
    assert values[47] == (base_time + timedelta(hours=47), 500 + 47 * 10)


@pytest.mark.asyncio
async def test_get_paired_observations(
    connection: None,
    forecast_with_values: int,
    sensor_with_measurements: int,
    base_time: datetime,
) -> None:
    pairs = await get_paired_observations(
        forecast_id=forecast_with_values,
        sensor_id=sensor_with_measurements,
        attribute=Attribute.AIR_TEMPERATURE,
    )

    # Should have 48 paired observations
    assert len(pairs) == 48

    # Check first pair: forecast=500, observed=450, error=50
    forecast_time, measured_at, forecast_val, observed_val = pairs[0]
    assert forecast_time == base_time
    assert measured_at == base_time
    assert forecast_val == 500
    assert observed_val == 450


@pytest.mark.asyncio
async def test_upsert_and_get_bias_stats(
    connection: None,
    location_id: int,
    sensor_id: int,
    forecast_id: int,
) -> None:
    # Create initial stats
    state = WelfordState()
    state.update(50.0)  # Error of 50 (0.5°C bias)
    state.update(60.0)

    await upsert_bias_stats(
        location_id=location_id,
        sensor_id=sensor_id,
        forecast_id=forecast_id,
        attribute=Attribute.AIR_TEMPERATURE,
        lead_time_bucket=0,
        state=state,
    )

    # Get the stats back
    stats = await get_bias_stats(
        location_id=location_id,
        forecast_id=forecast_id,
        attribute=Attribute.AIR_TEMPERATURE,
    )

    assert 0 in stats
    assert stats[0].count == 2
    assert stats[0].mean == 55.0


@pytest.mark.asyncio
async def test_upsert_merges_stats(
    connection: None,
    location_id: int,
    sensor_id: int,
    forecast_id: int,
) -> None:
    # Insert first batch
    state1 = WelfordState()
    state1.update(50.0)
    state1.update(60.0)

    await upsert_bias_stats(
        location_id=location_id,
        sensor_id=sensor_id,
        forecast_id=forecast_id,
        attribute=Attribute.AIR_TEMPERATURE,
        lead_time_bucket=0,
        state=state1,
    )

    # Insert second batch (should merge)
    state2 = WelfordState()
    state2.update(40.0)
    state2.update(50.0)

    await upsert_bias_stats(
        location_id=location_id,
        sensor_id=sensor_id,
        forecast_id=forecast_id,
        attribute=Attribute.AIR_TEMPERATURE,
        lead_time_bucket=0,
        state=state2,
    )

    # Check merged stats
    stats = await get_bias_stats(
        location_id=location_id,
        forecast_id=forecast_id,
        attribute=Attribute.AIR_TEMPERATURE,
    )

    assert stats[0].count == 4
    # Mean of [50, 60, 40, 50] = 50
    assert stats[0].mean == 50.0
