import json
import os
import textwrap
import threading
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from typing import Any, AsyncIterator, Iterable, Iterator, Optional, Sequence

import asyncpg
import structlog

from ..utils import timed

logger = structlog.get_logger()

current_connection: ContextVar[asyncpg.Connection[asyncpg.Record]] = ContextVar(
    "connection"
)

thread_local = threading.local()

SERVER_SETTINGS = {
    "timezone": "UTC",
}


@asynccontextmanager
async def setup() -> AsyncIterator[None]:
    """
    Configure database connectivity with a single connection.
    """

    dsn = os.environ.get("DATABASE_URL", None)

    con = await asyncpg.connect(dsn=dsn, server_settings=SERVER_SETTINGS)
    try:
        await initialize_connection(con)
        with set_connection(con):
            yield
    finally:
        await con.close()


async def connect() -> asyncpg.pool.Pool[asyncpg.Record]:
    assert getattr(thread_local, "connection_pool", None) is None
    dsn = os.environ.get("DATABASE_URL", None)
    pool = thread_local.connection_pool = await asyncpg.create_pool(
        dsn=dsn, server_settings=SERVER_SETTINGS, init=initialize_connection
    )
    assert pool is not None
    return pool


async def disconnect() -> None:
    assert getattr(thread_local, "connection_pool", None) is not None
    await thread_local.connection_pool.close()
    thread_local.connection_pool = None


@asynccontextmanager
async def setup_pool() -> AsyncIterator[None]:
    """
    Configure database connectivity with a connection pool.
    """

    await connect()
    try:
        yield
    finally:
        await disconnect()


@contextmanager
def set_connection(con: asyncpg.Connection[asyncpg.Record]) -> Iterator[None]:
    """
    Set the connection for the current task
    """

    logger.debug("Set current connection")
    reset_token = current_connection.set(con)
    try:
        yield
    finally:
        logger.debug("Release current connection")
        current_connection.reset(reset_token)


async def initialize_connection(con: asyncpg.Connection[asyncpg.Record]) -> None:
    """
    Hook to customize connections.
    """

    await con.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )


@asynccontextmanager
async def connection() -> AsyncIterator[asyncpg.Connection[asyncpg.Record]]:
    """
    Get or acquire a connection for connection for the current task.
    """

    # First try to use the connection assigned to this task
    try:
        connection = current_connection.get()
        logger.debug("Using existing connection")
        yield connection
    except LookupError:
        pass
    else:
        return

    # Fall back to leasing a connection from the connection pool. If this is
    # set we populate the context variable to ensure the same connection is
    # used e.g. when within a transactin block.
    if pool := getattr(thread_local, "connection_pool", None):
        logger.debug("Leasing connection from pool")
        async with pool.acquire() as con:
            with set_connection(con):
                yield con
        logger.debug("Released connection to pool")
    else:
        raise RuntimeError(
            "No connection or connection pool configured for current task"
        )


@asynccontextmanager
async def transaction() -> AsyncIterator[None]:
    """
    Start a new transaction. Use as a decorator or context manager.

    If a connection is assigned to the current context that is used,
    otherwise a new connection is leased from the connection pool.
    """

    async with connection() as con:
        async with con.transaction():
            yield


async def execute(sql: str, *args: Any, timeout: Optional[float] = None) -> str:
    async with connection() as con:
        with log_query(sql, args):
            return await con.execute(sql, *args, timeout=timeout)


async def executemany(
    sql: str, args: Iterable[Sequence[Any]], *, timeout: Optional[float] = None
) -> None:
    async with connection() as con:
        with log_query(sql, args):
            await con.executemany(sql, args, timeout=timeout)


async def fetch(
    sql: str, *args: Any, timeout: Optional[float] = None
) -> list[asyncpg.Record]:
    async with connection() as con:
        with log_query(sql, args):
            return await con.fetch(sql, *args, timeout=timeout)


async def fetchrow(
    sql: str, *args: Any, timeout: Optional[float] = None
) -> asyncpg.Record | None:
    async with connection() as con:
        with log_query(sql, args):
            return await con.fetchrow(sql, *args, timeout=timeout)


async def fetchval(
    sql: str, *args: Any, column: int = 0, timeout: Optional[float] = None
) -> Any:
    async with connection() as con:
        with log_query(sql, args):
            return await con.fetchval(sql, *args, column=column, timeout=timeout)


###########
# Helpers #
###########


@contextmanager
def log_query(sql: str, args: Any) -> Iterator[None]:
    with timed("Execute query", sql=textwrap.shorten(sql, 100)):
        yield
