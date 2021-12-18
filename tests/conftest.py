import os
import pathlib
import subprocess
from typing import AsyncIterator, Iterator

import asyncpg  # type: ignore
import pytest

from weather_station import db
from weather_station.accounts.queries import create_account
from weather_station.auth.models import Session
from weather_station.auth.queries import create_session

#######################
# Basic project setup #
#######################


@pytest.fixture(scope="session")
def setup_db() -> Iterator[None]:
    def run(*args: str | pathlib.Path) -> None:
        subprocess.run(args, check=True)

    os.environ["PGDATABASE"] = "weather_station_test"
    run("createdb", "weather_station_test")
    try:
        project_root = pathlib.Path(__file__).parent.parent
        migrate_script = project_root / "bin" / "migrate"
        migrations_dir = project_root / "weather_station" / "db" / "migrations"
        print("Applying migrations")
        for migrations_file in sorted(migrations_dir.glob("*.sql")):
            print(f"Applying {migrations_file}")
            run(migrate_script, migrations_file)

        yield
    finally:
        run("dropdb", "weather_station_test")


@pytest.fixture(scope="function")
async def _connection(setup_db) -> AsyncIterator[asyncpg.Connection]:
    connection = await asyncpg.connect()
    try:
        await db.initialize_connection(connection)
        transaction = connection.transaction()
        await transaction.start()
        try:
            yield connection
        finally:
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
async def account_id(connection, username: str, password: str) -> int:
    return await create_account(username=username, password=password)


############
# Sessions #
############


@pytest.fixture
async def session(connection, account_id: int) -> Session:
    return await create_session(account_id=account_id)
