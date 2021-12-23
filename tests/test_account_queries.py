import pytest

from heim.accounts.queries import create_account, create_location

pytestmark = pytest.mark.asyncio


async def test_create_account(connection, username, password) -> None:
    account_id = await create_account(username=username, password=password)
    assert account_id > 0


async def test_create_location(
    connection, account_id: int, coordinate: tuple[float, float]
) -> None:
    location_id = await create_location(
        account_id=account_id, name="test location", coordinate=coordinate
    )
    assert location_id > 0
