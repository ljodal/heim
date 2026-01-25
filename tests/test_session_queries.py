import pytest
from heim.auth.models import Session
from heim.auth.queries import (
    create_session,
    delete_session,
    get_session,
    update_session,
)

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


async def test_delete_session(connection: None, session: Session) -> None:
    """Test that delete_session removes the session from the database."""
    # Verify the session exists
    fetched = await get_session(key=session.key)
    assert fetched is not None

    # Delete the session
    await delete_session(session)

    # Verify the session no longer exists
    fetched = await get_session(key=session.key)
    assert fetched is None


async def test_multiple_concurrent_sessions(connection: None, account_id: int) -> None:
    """
    Test that creating a new session does not invalidate existing sessions.

    This verifies that a user can be logged in from multiple devices simultaneously.
    """
    # Create the first session (e.g., logging in on device A)
    session_a = await create_session(account_id=account_id)
    assert session_a.key
    assert session_a.account_id == account_id

    # Create a second session (e.g., logging in on device B)
    session_b = await create_session(account_id=account_id)
    assert session_b.key
    assert session_b.account_id == account_id

    # The two sessions should have different keys
    assert session_a.key != session_b.key

    # Both sessions should still be valid
    fetched_a = await get_session(key=session_a.key)
    fetched_b = await get_session(key=session_b.key)

    assert fetched_a is not None, "First session was invalidated"
    assert fetched_b is not None, "Second session should exist"
    assert fetched_a.account_id == account_id
    assert fetched_b.account_id == account_id
