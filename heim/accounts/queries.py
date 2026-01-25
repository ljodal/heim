from typing import cast

import asyncpg

from .. import db
from .models import Coordinate, Location
from .utils import hash_password


async def create_account(*, username: str, password: str) -> int:
    """Create a new account"""

    hashed_password = hash_password(password)

    value: int = await db.fetchval(
        "INSERT INTO account (username, password) VALUES ($1, $2) RETURNING id",
        username,
        hashed_password,
    )
    return value


async def get_account(*, username: str) -> tuple[int, str] | None:
    """
    Get an account based on username. Returns the account_id and password hash.
    """

    account: asyncpg.Record | None = await db.fetchrow(
        "SELECT id, password FROM account WHERE username = $1", username
    )
    return cast(tuple[int, str] | None, account)


async def create_location(
    *, account_id: int, name: str, coordinate: tuple[float, float]
) -> int:
    """Create a new location"""

    location_id: int = await db.fetchval(
        """
        INSERT INTO location (account_id, name, coordinate) VALUES ($1, $2, $3)
        RETURNING id
        """,
        account_id,
        name,
        coordinate,
    )
    return location_id


async def get_locations(*, account_id: int) -> list[Location]:
    locations = await db.fetch(
        "SELECT id, name, coordinate FROM location WHERE account_id = $1", account_id
    )
    return [
        Location(
            id=location_id,
            name=name,
            coordinate=Coordinate(longitude=longitude, latitude=latitude),
        )
        for location_id, name, (longitude, latitude) in locations
    ]


async def get_location(*, account_id: int, location_id: int) -> Location | None:
    """Get a single location by ID"""
    row = await db.fetchrow(
        "SELECT id, name, coordinate FROM location WHERE id = $1 AND account_id = $2",
        location_id,
        account_id,
    )
    if row is None:
        return None
    location_id, name, (longitude, latitude) = row
    return Location(
        id=location_id,
        name=name,
        coordinate=Coordinate(longitude=longitude, latitude=latitude),
    )


async def update_location(
    *, account_id: int, location_id: int, name: str, coordinate: tuple[float, float]
) -> None:
    """Update an existing location"""
    await db.execute(
        """
        UPDATE location
        SET name = $1, coordinate = $2
        WHERE id = $3 AND account_id = $4
        """,
        name,
        coordinate,
        location_id,
        account_id,
    )
