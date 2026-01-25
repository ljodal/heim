from datetime import datetime
from typing import Any, Self

import httpx
import structlog

from .exceptions import (
    EaseeAPIError,
    ExpiredAccessToken,
    InvalidCredentials,
    InvalidRefreshToken,
)
from .types import (
    Charger,
    ChargerState,
    ChargingSession,
    HourlyUsage,
    Site,
    TokenResponse,
)

logger = structlog.get_logger()

# Easee API endpoints
API_URL = "https://api.easee.com"


class EaseeClient:
    """
    A client for communicating with the Easee API.

    Uses httpx for async HTTP requests.
    """

    def __init__(self, *, access_token: str | None = None) -> None:
        self.access_token = access_token
        self.client: httpx.AsyncClient | None = None

    async def close(self) -> None:
        if self.client:
            await self.client.aclose()
            self.client = None

    ########
    # Auth #
    ########

    async def login(self, *, username: str, password: str) -> TokenResponse:
        """
        Login with username and password to get access tokens.
        """
        if not self.client:
            self.client = httpx.AsyncClient()

        response = await self.client.post(
            f"{API_URL}/api/accounts/login",
            json={"userName": username, "password": password},
        )

        if response.status_code == 401:
            raise InvalidCredentials("Invalid username or password")

        if response.status_code >= 400:
            error_text = response.text
            logger.error(f"Login failed: {response.status_code} - {error_text}")
            raise EaseeAPIError(f"Login failed: {response.status_code}")

        return TokenResponse.model_validate(response.json())

    async def refresh_token(self, *, refresh_token: str) -> TokenResponse:
        """
        Refresh an access token using a refresh token.
        """
        if not self.client:
            self.client = httpx.AsyncClient()

        response = await self.client.post(
            f"{API_URL}/api/accounts/refresh_token",
            json={
                "accessToken": self.access_token or "",
                "refreshToken": refresh_token,
            },
        )

        if response.status_code == 401:
            raise InvalidRefreshToken("Refresh token is invalid or expired")

        if response.status_code >= 400:
            error_text = response.text
            logger.error(f"Token refresh failed: {response.status_code} - {error_text}")
            raise EaseeAPIError(f"Token refresh failed: {response.status_code}")

        return TokenResponse.model_validate(response.json())

    ############
    # Chargers #
    ############

    async def get_chargers(self) -> list[Charger]:
        """
        Get all chargers accessible by the authenticated user.
        """
        data = await self._api_request("GET", "/api/chargers")
        return [Charger.model_validate(c) for c in data]

    async def get_charger_state(self, charger_id: str) -> ChargerState:
        """
        Get the current state of a charger.
        """
        data = await self._api_request("GET", f"/api/chargers/{charger_id}/state")
        return ChargerState.model_validate(data)

    #########
    # Sites #
    #########

    async def get_sites(self) -> list[Site]:
        """
        Get all sites accessible by the authenticated user.
        """
        data = await self._api_request("GET", "/api/sites")
        return [Site.model_validate(s) for s in data]

    ############
    # Sessions #
    ############

    async def get_sessions(
        self,
        charger_id: str,
        *,
        from_date: datetime,
        to_date: datetime,
    ) -> list[ChargingSession]:
        """
        Get charging sessions for a charger within a date range.
        """
        from_str = from_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        to_str = to_date.strftime("%Y-%m-%dT%H:%M:%SZ")

        data = await self._api_request(
            "GET",
            f"/api/sessions/charger/{charger_id}/sessions/{from_str}/{to_str}",
        )
        return [ChargingSession.model_validate(s) for s in data]

    #################
    # Hourly Usage #
    #################

    async def get_hourly_usage(
        self,
        charger_id: str,
        *,
        from_date: datetime,
        to_date: datetime,
    ) -> list[HourlyUsage]:
        """
        Get hourly energy usage for a charger within a date range.
        """
        from_str = from_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        to_str = to_date.strftime("%Y-%m-%dT%H:%M:%SZ")

        data = await self._api_request(
            "GET",
            f"/api/chargers/{charger_id}/usage/hourly/{from_str}/{to_str}",
        )
        return [HourlyUsage.model_validate(u) for u in data]

    ###################
    # Context manager #
    ###################

    async def __aenter__(self) -> Self:
        if not self.client:
            self.client = httpx.AsyncClient()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    ####################
    # Internal helpers #
    ####################

    async def _api_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        """
        Make an authenticated API request.
        """
        if not self.client:
            self.client = httpx.AsyncClient()

        if not self.access_token:
            raise EaseeAPIError("No access token available")

        response = await self.client.request(
            method,
            f"{API_URL}{path}",
            params=params,
            json=json,
            headers={"Authorization": f"Bearer {self.access_token}"},
        )

        if response.status_code == 401:
            raise ExpiredAccessToken("Access token has expired")

        if response.status_code == 403:
            raise EaseeAPIError(f"API request forbidden: {path}")

        if response.status_code >= 400:
            logger.error(
                "API request failed",
                path=path,
                status=response.status_code,
                response=response.text,
            )
            raise EaseeAPIError(f"API request failed: {response.status_code}")

        # Some endpoints return empty response
        if not response.text:
            return None

        return response.json()
