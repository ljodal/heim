from .. import db


async def create_account(*, username: str, hashed_password: str) -> int:
    """Create a new account"""

    return await db.fetchval(
        "INSERT INTO account (username, password) VALUES ($1, $2) RETURNING id",
        username,
        hashed_password,
    )


async def create_location(*, account_id: int, name: str) -> int:
    """Create a new location"""

    return await db.fetchval(
        "INSERT INTO location (account_id, name) VALUES ($1, $2) RETURNING id",
        account_id,
        name,
    )
