"""
Base API client with common httpx infrastructure.

Provides shared functionality for API clients:
- httpx.AsyncClient lifecycle management
- Async context manager support
- Pydantic response decoding helpers
"""

from typing import Any, Self

import httpx
from pydantic import BaseModel


class BaseAPIClient:
    """
    Base class for API clients using httpx.

    Handles the httpx.AsyncClient lifecycle and provides helpers for
    Pydantic response decoding. Subclasses implement their own auth
    and request logic.

    Attributes:
        access_token: OAuth access token (if using OAuth)
        client: The underlying httpx.AsyncClient (lazily initialized)
    """

    access_token: str | None
    client: httpx.AsyncClient | None

    def __init__(self, *, access_token: str | None = None) -> None:
        self.access_token = access_token
        self.client = None

    def _ensure_client(self) -> httpx.AsyncClient:
        """Get the httpx client, creating it if needed."""
        if not self.client:
            self.client = httpx.AsyncClient()
        return self.client

    async def close(self) -> None:
        """Close the httpx client and release resources."""
        if self.client:
            await self.client.aclose()
            self.client = None

    async def __aenter__(self) -> Self:
        self._ensure_client()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    # ==================
    # Response decoding
    # ==================

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
