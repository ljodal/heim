from .. import db
from .models import Location
from .utils import hash_password


async def create_account(*, username: str, password: str) -> int:
    """Create a new account"""

    hashed_password = hash_password(password)

    return await db.fetchval(
        "INSERT INTO account (username, password) VALUES ($1, $2) RETURNING id",
        username,
        hashed_password,
    )


async def get_account(*, username: str) -> tuple[int, str] | None:
    """
    Get an account based on username. Returns the account_id and password hash.
    """

    return await db.fetchrow(
        "SELECT id, password FROM account WHERE username = $1", username
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


async def get_locations(*, account_id: int) -> list[Location]:

    locations = await db.fetch(
        "SELECT id, name, coordinate FROM location WHERE account_id = $1", account_id
    )
    return [
        Location(
            id=location_id,
            name=name,
            coordinate={"longitude": longitude, "latitude": latitude},
        )
        for location_id, name, (longitude, latitude) in locations
    ]
