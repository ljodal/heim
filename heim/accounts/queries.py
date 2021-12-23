from .. import db
from .utils import hash_password


async def create_account(*, username: str, password: str) -> int:
    """Create a new account"""

    hashed_password = hash_password(password)

    return await db.fetchval(
        "INSERT INTO account (username, password) VALUES ($1, $2) RETURNING id",
        username,
        hashed_password,
    )


async def create_location(
    *, account_id: int, name: str, coordinate: tuple[float, float]
) -> int:
    """Create a new location"""

    return await db.fetchval(
        """
        INSERT INTO location (account_id, name, coordinate) VALUES ($1, $2, $3)
        RETURNING id
        """,
        account_id,
        name,
        coordinate,
    )


async def get_locations(*, account_id: int) -> list[tuple[int, str]]:

    return await db.fetch(
        "SELECT id, name FROM location WHERE account_id = $1", account_id
    )
