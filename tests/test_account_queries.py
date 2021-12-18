import pytest

from weather_station.accounts.queries import create_account, create_location

pytestmark = pytest.mark.asyncio


async def test_create_account(connection, username, hashed_password) -> None:
    account_id = await create_account(
        username=username, hashed_password=hashed_password
    )
    assert account_id > 0


async def test_create_location(connection, account_id: int) -> None:
    location_id = await create_location(account_id=account_id, name="test location")
    assert location_id > 0
