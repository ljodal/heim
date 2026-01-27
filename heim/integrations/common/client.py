"""Base API client with OAuth support."""

import functools
import inspect
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Concatenate, Protocol, Self, cast

import httpx
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


class BaseAPIClient(ABC):
    """Base class for API clients with OAuth token refresh support."""

    access_token: str | None
    client: httpx.AsyncClient

    def __init__(self, *, access_token: str | None = None) -> None:
        self.access_token = access_token
        self.client = httpx.AsyncClient()

    async def close(self) -> None:
        await self.client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    @classmethod
    @abstractmethod
    async def get_account(
        cls, account_id: int, *, for_update: bool = False
    ) -> OAuthAccount: ...

    @classmethod
    @abstractmethod
    async def update_account(
        cls,
        account: OAuthAccount,
        *,
        refresh_token: str,
        access_token: str,
        expires_at: datetime,
    ) -> None: ...

    @abstractmethod
    async def refresh_token(self, *, refresh_token: str) -> TokenResponse: ...

    @classmethod
    def authenticated[**P, R](
        cls,
    ) -> Callable[
        [Callable[Concatenate[Self, P], Awaitable[R]]],
        Callable[P, Awaitable[R]],
    ]:
        """Decorator that injects an authenticated client and handles token refresh."""

        def decorator(
            func: Callable[Concatenate[Self, P], Awaitable[R]],
        ) -> Callable[P, Awaitable[R]]:
            parameters = inspect.signature(func).parameters
            assert "account_id" in parameters, (
                f"Function {getattr(func, '__name__', repr(func))} "
                "must have 'account_id' keyword argument"
            )

            @functools.wraps(func)
            async def inner(*args: P.args, **kwargs: P.kwargs) -> R:
                account_id = cast(int, kwargs["account_id"])
                account = await cls.get_account(account_id)

                async with cls(access_token=account.access_token) as client:
                    try:
                        return await func(client, *args, **kwargs)
                    except ExpiredAccessToken:
                        logger.warning("Access token expired, refreshing")
                        await cls._refresh_access_token(client, account_id)
                        return await func(client, *args, **kwargs)

            return inner

        return decorator

    @classmethod
    async def _refresh_access_token(cls, client: Self, account_id: int) -> None:
        """Refresh the OAuth access token, handling row locking to prevent races."""
        async with db.connection() as con:
            if con.is_in_transaction():
                raise RuntimeError("Cannot refresh access token in a transaction")

            async with con.transaction():
                account = await cls.get_account(account_id, for_update=True)

                response = await client.refresh_token(
                    refresh_token=account.refresh_token
                )
                client.access_token = response.access_token

                await cls.update_account(
                    account,
                    refresh_token=response.refresh_token,
                    access_token=response.access_token,
                    expires_at=datetime.now(UTC)
                    + timedelta(seconds=response.expires_in),
                )
