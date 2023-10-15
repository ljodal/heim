import functools
import inspect
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import Concatenate, ParamSpec, TypeVar, cast

import structlog

from ... import db
from .client import AqaraClient
from .exceptions import ExpiredAccessToken
from .queries import get_aqara_account, update_aqara_account

P = ParamSpec("P")
R = TypeVar("R")

logger = structlog.get_logger()


def with_aqara_client(
    func: Callable[Concatenate[AqaraClient, P], Awaitable[R]]
) -> Callable[P, Awaitable[R]]:
    """
    A decorator that injects an aqara client to the decorated function. The
    decorated function must have an account_id keyword argument that will be
    used to look up the access token.

    This will also automatically refresh access tokens if it catches an
    ExpiredAccessToken exception and call the decorated function again with a
    new access token. Because of this decorated functions should be idempotent.
    """

    parameters = inspect.signature(func).parameters
    assert "account_id" in parameters

    @functools.wraps(func)
    async def inner(*args: P.args, **kwargs: P.kwargs) -> R:
        account_id = cast(int, kwargs["account_id"])
        account = await get_aqara_account(account_id=account_id)
        async with AqaraClient(access_token=account.access_token) as client:
            try:
                return await func(client, *args, **kwargs)
            except ExpiredAccessToken:
                logger.warning("Access token has expired, refreshing")
                # The access token has expired, so refresh it and retry
                await refresh_access_token(client, account_id=account_id)
                return await func(client, *args, **kwargs)

    return inner


async def refresh_access_token(client: AqaraClient, *, account_id: int) -> None:
    """
    Refresh the aqara access token for the given account.
    """

    async with db.connection() as con:
        if con.is_in_transaction():
            raise RuntimeError("Cannot refresh access token in a transaction")

        async with con.transaction():
            account = await get_aqara_account(account_id=account_id, for_update=True)

            response = await client.refresh_token(refresh_token=account.refresh_token)
            client.access_token = response.access_token

            await update_aqara_account(
                account,
                refresh_token=response.refresh_token,
                access_token=response.access_token,
                expires_at=(
                    datetime.now(timezone.utc) + timedelta(seconds=response.expires_in)
                ),
            )
