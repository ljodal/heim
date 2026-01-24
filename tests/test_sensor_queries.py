from datetime import UTC, datetime, timedelta

import pytest
from heim import db
from heim.sensors.queries import (
    add_exclusion,
    get_measurements,
    list_exclusions,
    remove_exclusion,
    save_measurements,
)
from heim.sensors.types import Attribute

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def sensor_id(connection: None, account_id: int, location_id: int) -> int:
    """Create a basic sensor for testing."""
    sensor_id: int = await db.fetchval(
        """
        INSERT INTO sensor (account_id, location_id, name)
        VALUES ($1, $2, $3)
        RETURNING id
        """,
        account_id,
        location_id,
        "Test sensor",
    )
    return sensor_id


@pytest.fixture
async def sensor_with_measurements(sensor_id: int) -> int:
    """Create a sensor with hourly measurements for the last 48 hours."""
    now = datetime.now(UTC)
    measurements = [
        (Attribute.AIR_TEMPERATURE, now - timedelta(hours=i), 2000 + i * 10)
        for i in range(48)
    ]
    await save_measurements(sensor_id=sensor_id, values=measurements)
    return sensor_id


async def test_get_measurements_returns_measurements(
    connection: None, sensor_with_measurements: int
) -> None:
    measurements = await get_measurements(
        sensor_id=sensor_with_measurements,
        attribute=Attribute.AIR_TEMPERATURE,
        hours=24,
    )
    assert len(measurements) == 24


async def test_get_measurements_excludes_measurements_in_exclusion_range(
    connection: None, account_id: int, sensor_with_measurements: int
) -> None:
    now = datetime.now(UTC)

    await add_exclusion(
        account_id=account_id,
        sensor_id=sensor_with_measurements,
        from_time=now - timedelta(hours=12),
        until_time=now - timedelta(hours=6),
    )

    measurements = await get_measurements(
        sensor_id=sensor_with_measurements,
        attribute=Attribute.AIR_TEMPERATURE,
        hours=24,
    )
    # Should have 24 - 6 = 18 measurements (6 excluded)
    assert len(measurements) == 18


async def test_get_measurements_with_multiple_exclusion_ranges(
    connection: None, account_id: int, sensor_with_measurements: int
) -> None:
    now = datetime.now(UTC)

    await add_exclusion(
        account_id=account_id,
        sensor_id=sensor_with_measurements,
        from_time=now - timedelta(hours=6),
        until_time=now - timedelta(hours=4),
    )
    await add_exclusion(
        account_id=account_id,
        sensor_id=sensor_with_measurements,
        from_time=now - timedelta(hours=12),
        until_time=now - timedelta(hours=10),
    )

    measurements = await get_measurements(
        sensor_id=sensor_with_measurements,
        attribute=Attribute.AIR_TEMPERATURE,
        hours=24,
    )
    # Should have 24 - 2 - 2 = 20 measurements
    assert len(measurements) == 20


async def test_add_exclusion_creates_exclusion(
    connection: None, account_id: int, sensor_id: int
) -> None:
    now = datetime.now(UTC)
    exclusion_id = await add_exclusion(
        account_id=account_id,
        sensor_id=sensor_id,
        from_time=now - timedelta(hours=2),
        until_time=now - timedelta(hours=1),
    )
    assert exclusion_id is not None
    assert exclusion_id > 0


async def test_add_exclusion_returns_none_for_wrong_account(
    connection: None, account_id: int, sensor_id: int
) -> None:
    now = datetime.now(UTC)
    exclusion_id = await add_exclusion(
        account_id=account_id + 999,
        sensor_id=sensor_id,
        from_time=now - timedelta(hours=2),
        until_time=now - timedelta(hours=1),
    )
    assert exclusion_id is None


async def test_list_exclusions(
    connection: None, account_id: int, sensor_id: int
) -> None:
    now = datetime.now(UTC)

    await add_exclusion(
        account_id=account_id,
        sensor_id=sensor_id,
        from_time=now - timedelta(hours=4),
        until_time=now - timedelta(hours=3),
    )
    await add_exclusion(
        account_id=account_id,
        sensor_id=sensor_id,
        from_time=now - timedelta(hours=2),
        until_time=now - timedelta(hours=1),
    )

    exclusions = await list_exclusions(account_id=account_id, sensor_id=sensor_id)
    assert len(exclusions) == 2


async def test_list_exclusions_returns_empty_for_wrong_account(
    connection: None, account_id: int, sensor_id: int
) -> None:
    now = datetime.now(UTC)

    await add_exclusion(
        account_id=account_id,
        sensor_id=sensor_id,
        from_time=now - timedelta(hours=2),
        until_time=now - timedelta(hours=1),
    )

    exclusions = await list_exclusions(account_id=account_id + 999, sensor_id=sensor_id)
    assert len(exclusions) == 0


async def test_remove_exclusion(
    connection: None, account_id: int, sensor_id: int
) -> None:
    now = datetime.now(UTC)

    exclusion_id = await add_exclusion(
        account_id=account_id,
        sensor_id=sensor_id,
        from_time=now - timedelta(hours=2),
        until_time=now - timedelta(hours=1),
    )
    assert exclusion_id is not None

    result = await remove_exclusion(account_id=account_id, exclusion_id=exclusion_id)
    assert result is True

    exclusions = await list_exclusions(account_id=account_id, sensor_id=sensor_id)
    assert len(exclusions) == 0


async def test_remove_exclusion_returns_false_for_wrong_account(
    connection: None, account_id: int, sensor_id: int
) -> None:
    now = datetime.now(UTC)

    exclusion_id = await add_exclusion(
        account_id=account_id,
        sensor_id=sensor_id,
        from_time=now - timedelta(hours=2),
        until_time=now - timedelta(hours=1),
    )
    assert exclusion_id is not None

    result = await remove_exclusion(
        account_id=account_id + 999, exclusion_id=exclusion_id
    )
    assert result is False

    exclusions = await list_exclusions(account_id=account_id, sensor_id=sensor_id)
    assert len(exclusions) == 1
