import threading
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from typing import (
    Any,
    AsyncContextManager,
    AsyncIterator,
    Callable,
    Iterable,
    Iterator,
    Optional,
    Sequence,
    TypeVar,
    overload,
)

import asyncpg  # type: ignore

T = TypeVar("T", bound=asyncpg.Record)

current_connection: ContextVar[asyncpg.Connection] = ContextVar("connection")

local_data = threading.local()


@contextmanager
def set_connection(con: asyncpg.Connection) -> Iterator[None]:
    """
    Set the connection for the current task
    """

    reset_token = current_connection.set(con)
    yield
    current_connection.reset(reset_token)


# Mypy doesn't understand the typing, so teach it
connection: Callable[[], AsyncContextManager[asyncpg.Connection]]


@asynccontextmanager  # type: ignore
async def connection() -> AsyncIterator[asyncpg.Connection]:
    """
    Get or aquire a connection for connection for the current task.
    """

    # First try to use the connection assigned to this task
    try:
        yield current_connection.get()
    except LookupError:
        pass
    else:
        return

    # Fall back to leasing a connection from the connection pool. If this is
    # set we populate the context variable to ensure the same connection is
    # used e.g. when within a transactin block.
    if pool := getattr(local_data, "connection_pool", None):
        async with pool.aquire() as con:
            with set_connection(con):
                yield con
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
        return await con.execute(sql, *args, timeout=timeout)


async def executemany(
    sql: str, args: Iterable[Sequence], *, timeout: Optional[float] = None
) -> str:
    async with connection() as con:
        return await con.execute(sql, args, timeout=timeout)


@overload
async def fetch(
    sql: str, *args: Any, timeout: Optional[float] = ..., record_class: None = ...
) -> asyncpg.Record:
    ...


@overload
async def fetch(
    sql: str, *args: Any, timeout: Optional[float] = ..., record_class: T = ...
) -> list[T]:
    ...


async def fetch(
    sql: str,
    *args: Any,
    timeout: Optional[float] = None,
    record_class: Optional[T] = None,
) -> list[T]:
    async with connection() as con:
        return await con.fetch(sql, *args, timeout=timeout, record_class=record_class)


@overload
async def fetchrow(
    sql: str, *args: Any, timeout: Optional[float] = ..., record_class: None = ...
) -> asyncpg.Record:
    ...


@overload
async def fetchrow(
    sql: str, *args: Any, timeout: Optional[float] = ..., record_class: T = ...
) -> T:
    ...


async def fetchrow(
    sql: str,
    *args: Any,
    timeout: Optional[float] = None,
    record_class: Optional[T] = None,
) -> T:
    async with connection() as con:
        return await con.fetchrow(
            sql, *args, timeout=timeout, record_class=record_class
        )


async def fetchval(
    sql: str,
    *args: Any,
    column: int = 0,
    timeout: Optional[float] = None,
) -> T:
    async with connection() as con:
        return await con.fetchval(sql, *args, column=column, timeout=timeout)
