from .. import db
from .models import Session


async def get_session(*, key: str) -> Session | None:
    row = await db.fetchrow(
        "SELECT account_id, data FROM session WHERE key = $1",
        key,
    )

    return Session(key=key, **row) if row else None


async def create_session(*, account_id: int) -> Session:
    """
    Create a new session for the given account
    """

    key: str = await db.fetchval(
        """
        INSERT INTO session (account_id, data)
        VALUES ($1, '{}')
        RETURNING key
        """,
        account_id,
    )

    return Session(key=key, account_id=account_id, data={})


async def update_session(session: Session) -> None:
    """
    Update an existing session
    """

    await db.execute(
        "UPDATE session SET data=$1::jsonb WHERE key = $2",
        session.data,
        session.key,
    )
