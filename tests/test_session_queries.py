import pytest

from heim.auth.models import Session
from heim.auth.queries import create_session, get_session, update_session

pytestmark = pytest.mark.asyncio


async def test_create_session(connection: None, account_id: int) -> None:
    session = await create_session(account_id=account_id)
    assert session.key
    assert session.data == {}


async def test_get_session(connection: None, session: Session) -> None:
    fetched_session = await get_session(key=session.key)
    assert session == fetched_session


async def test_update_session(connection: None, session: Session) -> None:
    assert session.data == {}
    session.data["foo"] = "bar"
    await update_session(session)
    fetched_session = await get_session(key=session.key)
    assert session == fetched_session
