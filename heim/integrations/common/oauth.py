"""
Generic OAuth token refresh utilities for integrations.

This module provides utilities for handling OAuth token refresh across
different integrations. It defines protocols that clients and accounts
must implement, and provides a decorator factory for automatic token refresh.
"""

import functools
import inspect
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Concatenate, Protocol, cast

import structlog

from ... import db
from .exceptions import ExpiredAccessToken

logger = structlog.get_logger()


class OAuthAccount(Protocol):
    """Protocol for OAuth account models stored in the database."""

    id: int
    account_id: int
    access_token: str
    refresh_token: str
    expires_at: datetime


class TokenResponse(Protocol):
    """Protocol for token refresh responses from OAuth APIs."""

    access_token: str
    refresh_token: str
    expires_in: int


class OAuthClient[TokenResponseT: TokenResponse](Protocol):
    """Protocol for OAuth API clients that support token refresh."""

    access_token: str | None

    async def refresh_token(self, *, refresh_token: str) -> TokenResponseT: ...

    async def __aenter__(self) -> "OAuthClient[TokenResponseT]": ...

    async def __aexit__(self, *args: object) -> None: ...


# Type aliases for the callback functions
type GetAccount[AccountT: OAuthAccount] = Callable[[int, bool], Awaitable[AccountT]]
type UpdateAccount[AccountT: OAuthAccount] = Callable[
    [AccountT, str, str, datetime], Awaitable[object]
]


async def refresh_access_token[
    ClientT: OAuthClient[TokenResponse],
    AccountT: OAuthAccount,
](
    client: ClientT,
    *,
    account_id: int,
    get_account: GetAccount[AccountT],
    update_account: UpdateAccount[AccountT],
) -> None:
    """
    Refresh the OAuth access token for an account.

    This function handles the complexity of:
    - Ensuring we're not already in a transaction (to avoid deadlocks)
    - Acquiring a row lock on the account to prevent concurrent refreshes
    - Updating both the client and database with new tokens

    Args:
        client: The API client whose token needs refreshing
        account_id: The account ID to refresh tokens for
        get_account: Callback to fetch the account. Called as:
            get_account(account_id, for_update)
        update_account: Callback to update account tokens. Called as:
            update_account(account, refresh_token, access_token, expires_at)
    """
    async with db.connection() as con:
        if con.is_in_transaction():
            raise RuntimeError("Cannot refresh access token in a transaction")

        async with con.transaction():
            account = await get_account(account_id, True)

            response = await client.refresh_token(refresh_token=account.refresh_token)
            client.access_token = response.access_token

            await update_account(
                account,
                response.refresh_token,
                response.access_token,
                datetime.now(UTC) + timedelta(seconds=response.expires_in),
            )


def create_oauth_decorator[
    ClientT: OAuthClient[TokenResponse],
    AccountT: OAuthAccount,
    **P,
    R,
](
    *,
    create_client: Callable[[str], ClientT],
    get_account: Callable[[int], Awaitable[AccountT]],
    get_account_for_update: GetAccount[AccountT],
    update_account: UpdateAccount[AccountT],
) -> Callable[
    [Callable[Concatenate[ClientT, P], Awaitable[R]]],
    Callable[P, Awaitable[R]],
]:
    """
    Create a decorator that injects an OAuth client and handles token refresh.

    The decorator:
    1. Looks up the account by account_id (from kwargs)
    2. Creates a client with the access token
    3. Executes the decorated function
    4. On ExpiredAccessToken, refreshes the token and retries once

    Args:
        create_client: Factory to create a client with an access token
        get_account: Fetch account by account_id (without row lock)
        get_account_for_update: Fetch account with row lock for token refresh
        update_account: Update account tokens after refresh

    Returns:
        A decorator for functions that take the client as first argument
        and have an account_id keyword argument.

    Example:
        with_my_client = create_oauth_decorator(
            create_client=lambda token: MyClient(access_token=token),
            get_account=lambda id: get_my_account(account_id=id),
            get_account_for_update=lambda id, lock: get_my_account(
                account_id=id, for_update=lock
            ),
            update_account=lambda acc, rt, at, exp: update_my_account(
                acc, refresh_token=rt, access_token=at, expires_at=exp
            ),
        )

        @with_my_client
        async def fetch_data(client: MyClient, *, account_id: int) -> Data:
            return await client.get_data()
    """

    def decorator(
        func: Callable[Concatenate[ClientT, P], Awaitable[R]],
    ) -> Callable[P, Awaitable[R]]:
        parameters = inspect.signature(func).parameters
        assert "account_id" in parameters, (
            f"Function {getattr(func, '__name__', repr(func))} "
            "must have 'account_id' keyword argument"
        )

        @functools.wraps(func)
        async def inner(*args: P.args, **kwargs: P.kwargs) -> R:
            account_id = cast(int, kwargs["account_id"])
            account = await get_account(account_id)

            # Cast needed because Protocol's __aenter__ returns the Protocol type,
            # not the concrete ClientT type that create_client returns
            async with create_client(account.access_token) as _client:
                client = cast(ClientT, _client)
                try:
                    return await func(client, *args, **kwargs)
                except ExpiredAccessToken:
                    logger.warning("Access token has expired, refreshing")
                    await refresh_access_token(
                        client,
                        account_id=account_id,
                        get_account=get_account_for_update,
                        update_account=update_account,
                    )
                    return await func(client, *args, **kwargs)

        return inner

    return decorator
