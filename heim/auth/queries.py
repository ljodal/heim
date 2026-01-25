from datetime import UTC, datetime, timedelta

from .. import db
from .models import Session

# Session lifetime: 30 days
SESSION_LIFETIME = timedelta(days=30)


async def get_session(*, key: str) -> Session | None:
    """
    Get a session by key. Returns None if the session doesn't exist or is expired.
    """
    row = await db.fetchrow(
        "SELECT account_id, data, expires_at FROM session WHERE key = $1",
        key,
    )

    if row is None:
        return None

    # Check if the session has expired
    if row["expires_at"] < datetime.now(UTC):
        return None

    return Session(key=key, **row)


async def create_session(*, account_id: int) -> Session:
    """
    Create a new session for the given account with a 30-day expiration.
    """
    expires_at = datetime.now(UTC) + SESSION_LIFETIME

    key: str = await db.fetchval(
        """
        INSERT INTO session (account_id, data, expires_at)
        VALUES ($1, '{}', $2)
        RETURNING key
        """,
        account_id,
        expires_at,
    )

    return Session(key=key, account_id=account_id, data={}, expires_at=expires_at)


async def update_session(session: Session) -> None:
    """
    Update an existing session's data.
    """
    await db.execute(
        "UPDATE session SET data=$1::jsonb WHERE key = $2",
        session.data,
        session.key,
    )


async def refresh_session(session: Session) -> None:
    """
    Extend the session expiration if it hasn't been refreshed recently.

    Only refreshes if the session hasn't been updated in the last hour,
    to avoid unnecessary database writes on every request.
    """
    time_remaining = session.expires_at - datetime.now(UTC)
    time_since_refresh = SESSION_LIFETIME - time_remaining
    if time_since_refresh < timedelta(hours=1):
        return

    new_expires_at = datetime.now(UTC) + SESSION_LIFETIME
    await db.execute(
        "UPDATE session SET expires_at = $1 WHERE key = $2",
        new_expires_at,
        session.key,
    )
    session.expires_at = new_expires_at


async def delete_session(session: Session) -> None:
    """
    Delete a session
    """

    await db.execute("DELETE FROM session WHERE key = $1", session.key)
