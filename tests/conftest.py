from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator, Iterator

import asyncpg
import httpx
import pytest

from heim import db
from heim.accounts.queries import create_account, create_location
from heim.auth.models import Session
from heim.auth.queries import create_session
from heim.db.migrations import migrate_db
from heim.server import app


def pytest_configure(config: pytest.Config) -> None:
    os.environ.setdefault("AQARA_APP_ID", "foo")
    os.environ.setdefault("AQARA_APP_KEY", "foo")
    os.environ.setdefault("AQARA_KEY_ID", "foo")
    os.environ.setdefault("AQARA_DOMAIN", "aqara.example.com")


def pytest_sessionfinish() -> None:
    """
    Silence exceptions raised when logging during atexit callbacks

    When pytest is capturing logging the log stream is closed before the
    process exits, but the Sentry SDK will log a message causing an exception
    """

    logging.raiseExceptions = False


#######################
# Basic project setup #
#######################


async def _setup_db() -> None:
    con = await asyncpg.connect(database="postgres")
    try:
        try:
            await con.execute("CREATE DATABASE heim_test")
        except asyncpg.exceptions.DuplicateDatabaseError:
            pass
        await migrate_db()
    finally:
        await con.close()


async def _drop_db() -> None:
    con = await asyncpg.connect(database="postgres")
    try:
        await con.execute("DROP DATABASE heim_test")
    finally:
        await con.close()


@pytest.fixture(scope="session")
def setup_db() -> Iterator[None]:
    os.environ["PGDATABASE"] = "heim_test"

    asyncio.run(_setup_db())
    try:
        yield
    finally:
        asyncio.run(_drop_db())


@pytest.fixture
async def _connection(
    setup_db: None,
) -> AsyncIterator[asyncpg.Connection[asyncpg.Record]]:
    connection = await asyncpg.connect()
    try:
        await db.initialize_connection(connection)
        transaction = connection.transaction()
        await transaction.start()
        try:
            print("Transaction started")
            yield connection
        finally:
            print("Rolling back")
            await transaction.rollback()
    finally:
        await connection.close()


@pytest.fixture
def connection(
    _connection: asyncpg.Connection[asyncpg.Record],
) -> Iterator[asyncpg.Connection[asyncpg.Record]]:
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
async def account_id(connection: None, username: str, password: str) -> int:
    return await create_account(username=username, password=password)


@pytest.fixture
def coordinate() -> tuple[float, float]:
    return (59.9171, 10.7276)


@pytest.fixture
async def location_id(
    connection: None, account_id: int, coordinate: tuple[float, float]
) -> int:
    return await create_location(
        account_id=account_id, name="Test location", coordinate=coordinate
    )


############
# Sessions #
############


@pytest.fixture
async def session(connection: None, account_id: int) -> Session:
    return await create_session(account_id=account_id)


########
# APIs #
########


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(app=app, base_url="http://test") as c:
        yield c


@pytest.fixture
async def authenticated_client(session: Session) -> AsyncIterator[httpx.AsyncClient]:
    headers = {"Authorization": f"Bearer {session.key}"}

    async with httpx.AsyncClient(app=app, base_url="http://test", headers=headers) as c:
        yield c
