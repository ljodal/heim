from datetime import UTC, datetime, timedelta

import pytest
from heim.auth.models import Session
from heim.auth.queries import (
    SESSION_LIFETIME,
    create_session,
    delete_session,
    get_session,
    refresh_session,
    update_session,
)

pytestmark = pytest.mark.asyncio


async def test_create_session(connection: None, account_id: int) -> None:
    session = await create_session(account_id=account_id)
    assert session.key
    assert session.data == {}
    # Session should have an expiration roughly 30 days in the future
    expected_expiration = datetime.now(UTC) + SESSION_LIFETIME
    assert abs((session.expires_at - expected_expiration).total_seconds()) < 5


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


async def test_expired_session_returns_none(connection: None, account_id: int) -> None:
    """Test that get_session returns None for expired sessions."""
    from heim import db

    # Create a session
    session = await create_session(account_id=account_id)

    # Manually set the expiration to the past
    await db.execute(
        "UPDATE session SET expires_at = $1 WHERE key = $2",
        datetime.now(UTC) - timedelta(hours=1),
        session.key,
    )

    # get_session should return None for expired sessions
    fetched = await get_session(key=session.key)
    assert fetched is None


async def test_refresh_session_extends_expiration(
    connection: None, session: Session
) -> None:
    """Test that refresh_session extends expiration if last refresh > 1 hour ago."""
    from heim import db

    # Set expiration to 1 day from now (simulates session refreshed ~29 days ago)
    old_expiration = datetime.now(UTC) + timedelta(days=1)
    await db.execute(
        "UPDATE session SET expires_at = $1 WHERE key = $2",
        old_expiration,
        session.key,
    )
    session.expires_at = old_expiration

    # Refresh the session
    await refresh_session(session)

    # The expiration should be extended to SESSION_LIFETIME from now
    expected_expiration = datetime.now(UTC) + SESSION_LIFETIME
    assert abs((session.expires_at - expected_expiration).total_seconds()) < 5

    # Verify the database was updated
    fetched = await get_session(key=session.key)
    assert fetched is not None
    assert abs((fetched.expires_at - expected_expiration).total_seconds()) < 5


async def test_refresh_session_skips_if_recently_refreshed(
    connection: None, session: Session
) -> None:
    """Test that refresh_session does nothing if refreshed less than 1 hour ago."""
    # A freshly created session has expires_at = now + SESSION_LIFETIME,
    # meaning it was just refreshed (time_since_refresh ≈ 0)
    original_expiration = session.expires_at

    # Refresh should be a no-op
    await refresh_session(session)

    # Expiration should be unchanged
    assert session.expires_at == original_expiration
