import os
import pathlib
import subprocess
from typing import AsyncIterator, Iterator

import asyncpg  # type: ignore
import pytest

from weather_station import db
from weather_station.accounts.queries import create_account
from weather_station.accounts.utils import hash_password

#######################
# Basic project setup #
#######################


@pytest.fixture(scope="session")
def setup_db() -> Iterator[None]:
    def run(*args: str | pathlib.Path) -> None:
        subprocess.run(args, check=True, capture_output=True)

    os.environ["PGDATABASE"] = "weather_station_test"
    run("createdb", "weather_station_test")
    migrate_script = pathlib.Path(__file__).parent.parent / "bin" / "migrate"
    migrations_dir = pathlib.Path(__file__).parent.parent / "db" / "migrations"
    for migrations_file in sorted(migrations_dir.glob("*.sql")):
        run(migrate_script, migrations_file)

    yield

    run("dropdb", "weather_station_test")


@pytest.fixture(scope="function")
async def _connection() -> AsyncIterator[asyncpg.Connection]:
    connection = await asyncpg.connect()
    try:
        transaction = connection.transaction()
        await transaction.start()
        yield connection
        await transaction.rollback()
    finally:
        await connection.close()


@pytest.fixture(scope="function")
def connection(_connection: asyncpg.Connection) -> Iterator[asyncpg.Connection]:
    # We have to set the contextvar in a sync fixture, because async pytest
    # fixtures are executed in a separate task which means they don't share
    # context with the test function.
    with db.set_connection(_connection):
        yield _connection


############
# Accounts #
############


@pytest.fixture
def username() -> str:
    return "test@example.com"


@pytest.fixture
def password() -> str:
    return "password"


@pytest.fixture
def hashed_password(password) -> str:
    return hash_password(password, iterations=1)


@pytest.fixture
async def account_id(connection, username: str, hashed_password: str) -> int:
    return await create_account(username=username, hashed_password=hashed_password)