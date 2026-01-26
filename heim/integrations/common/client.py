"""
Base API client with OAuth support.

Provides shared functionality for API clients:
- httpx.AsyncClient lifecycle management
- Async context manager support
- Pydantic response decoding helpers
- OAuth token refresh with automatic retry decorator
"""

import functools
import inspect
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Concatenate, Protocol, Self, cast

import httpx
import structlog
from pydantic import BaseModel

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
    """
    Base class for API clients using httpx with OAuth support.

    Subclasses must implement:
    - get_account: Fetch account from database
    - update_account: Update account tokens in database
    - refresh_token: Call the API to refresh the access token

    Then use the `authenticated()` class method as a decorator:

        @AqaraClient.authenticated()
        async def fetch_data(client: AqaraClient, *, account_id: int) -> Data:
            return await client.get_data()
    """

    access_token: str | None
    client: httpx.AsyncClient

    def __init__(self, *, access_token: str | None = None) -> None:
        self.access_token = access_token
        self.client = httpx.AsyncClient()

    async def close(self) -> None:
        """Close the httpx client and release resources."""
        await self.client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    # ======================
    # Abstract methods
    # ======================

    @classmethod
    @abstractmethod
    async def get_account(
        cls, account_id: int, *, for_update: bool = False
    ) -> OAuthAccount:
        """Fetch the OAuth account from the database."""
        ...

    @classmethod
    @abstractmethod
    async def update_account(
        cls,
        account: OAuthAccount,
        *,
        refresh_token: str,
        access_token: str,
        expires_at: datetime,
    ) -> None:
        """Update the OAuth account tokens in the database."""
        ...

    @abstractmethod
    async def refresh_token(self, *, refresh_token: str) -> TokenResponse:
        """Call the API to refresh the access token."""
        ...

    # ======================
    # OAuth decorator
    # ======================

    @classmethod
    def authenticated[**P, R](
        cls,
    ) -> Callable[
        [Callable[Concatenate[Self, P], Awaitable[R]]],
        Callable[P, Awaitable[R]],
    ]:
        """
        Decorator that injects an authenticated client and handles token refresh.

        The decorated function must have an `account_id` keyword argument.
        On ExpiredAccessToken, the token is refreshed and the function retried.
        Because of this, decorated functions should be idempotent.

        Example:
            @MyClient.authenticated()
            async def fetch_data(client: MyClient, *, account_id: int) -> Data:
                return await client.get_data()
        """

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
        """
        Refresh the OAuth access token for an account.

        Handles the complexity of:
        - Ensuring we're not already in a transaction (to avoid deadlocks)
        - Acquiring a row lock on the account to prevent concurrent refreshes
        - Updating both the client and database with new tokens
        """
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

    # ======================
    # Response decoding
    # ======================

    def _decode_json[T: BaseModel](
        self, response: httpx.Response, response_type: type[T]
    ) -> T:
        """
        Decode a JSON response into a Pydantic model.

        Uses model_validate_json for efficiency (single parse).
        """
        return response_type.model_validate_json(response.text)

    def _decode_json_field[T: BaseModel](
        self, response: httpx.Response, response_type: type[T], field: str
    ) -> T:
        """
        Decode a nested field from a JSON response into a Pydantic model.

        Useful when the API wraps the response in a container like {"body": ...}.
        """
        data = response.json()
        return response_type.model_validate(data[field])
