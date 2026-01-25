import os
from datetime import UTC, datetime
from typing import Any, Self

import httpx
import structlog

from .exceptions import (
    ExpiredAccessToken,
    InvalidGrant,
    InvalidRefreshToken,
    NetatmoAPIError,
)
from .types import (
    MeasureResponse,
    StationsDataResponse,
    TokenResponse,
)

logger = structlog.get_logger()

# Netatmo API endpoints
AUTH_URL = "https://api.netatmo.com/oauth2/token"
API_URL = "https://api.netatmo.com/api"


class NetatmoClient:
    """
    A client for communicating with the Netatmo API.
    """

    def __init__(self, *, access_token: str | None = None) -> None:
        self.client_id = getenv("NETATMO_CLIENT_ID")
        self.client_secret = getenv("NETATMO_CLIENT_SECRET")
        self.access_token = access_token
        self.client: httpx.AsyncClient | None = None

    async def close(self) -> None:
        if self.client:
            await self.client.aclose()
            self.client = None

    ########
    # Auth #
    ########

    async def get_token_from_code(
        self, *, code: str, redirect_uri: str
    ) -> TokenResponse:
        """
        Exchange an authorization code for access and refresh tokens.
        """
        return await self._token_request(
            grant_type="authorization_code",
            code=code,
            redirect_uri=redirect_uri,
        )

    async def refresh_token(self, *, refresh_token: str) -> TokenResponse:
        """
        Refresh an access token using a refresh token.
        """
        return await self._token_request(
            grant_type="refresh_token",
            refresh_token=refresh_token,
        )

    async def _token_request(self, **data: str) -> TokenResponse:
        """
        Make a token request to the Netatmo OAuth endpoint.
        """
        if not self.client:
            self.client = httpx.AsyncClient()

        request_data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            **data,
        }

        # Debug: log client_id prefix to verify it's being read
        logger.info(
            f"Token request with client_id starting with: {self.client_id[:8]}..."
        )

        response = await self.client.post(AUTH_URL, data=request_data)

        if response.status_code >= 400:
            try:
                error_data = response.json()
            except Exception:
                error_data = {"raw": response.text}
            logger.error(f"Token request failed: {response.status_code} - {error_data}")
            error = error_data.get("error", "")
            error_description = error_data.get("error_description", "")
            if error == "invalid_grant":
                grant_type = data.get("grant_type", "")
                if grant_type == "refresh_token":
                    raise InvalidRefreshToken(
                        f"Refresh token is invalid or expired: {error_description}"
                    )
                else:
                    raise InvalidGrant(
                        f"Authorization code is invalid, expired, or already used: "
                        f"{error_description}"
                    )
            if error == "invalid_client":
                raise NetatmoAPIError(
                    f"Invalid client credentials. Please verify NETATMO_CLIENT_ID "
                    f"and NETATMO_CLIENT_SECRET are correct. "
                    f"Client ID starts with: {self.client_id[:8]}..."
                )
            raise NetatmoAPIError(
                f"Token request failed: {error} - {error_description}"
            )

        return TokenResponse.model_validate(response.json())

    ################
    # Station data #
    ################

    async def get_stations_data(
        self, *, device_id: str | None = None
    ) -> StationsDataResponse:
        """
        Get data from all weather stations, or a specific device.
        """
        params: dict[str, str] = {}
        if device_id:
            params["device_id"] = device_id

        data = await self._api_request("getstationsdata", params=params)
        return StationsDataResponse.model_validate(data["body"])

    async def get_measure(
        self,
        *,
        device_id: str,
        module_id: str | None = None,
        scale: str,
        measure_types: list[str],
        date_begin: datetime | None = None,
        date_end: datetime | None = None,
    ) -> dict[str, list[tuple[datetime, float | None]]]:
        """
        Get historical measurements for a device/module.

        Automatically paginates through results since the API limits responses
        to 1024 data points per request.

        Args:
            device_id: The station ID
            module_id: The module ID (None for main station)
            scale: Time scale (max, 30min, 1hour, 3hours, 1day, 1week, 1month)
            measure_types: List of measure types (Temperature, Humidity, etc.)
            date_begin: Start of period (optional)
            date_end: End of period (optional)

        Returns:
            Dict mapping measure type to list of (timestamp, value) tuples
        """
        result: dict[str, list[tuple[datetime, float | None]]] = {
            measure_type: [] for measure_type in measure_types
        }

        current_begin = int(date_begin.timestamp()) if date_begin else None
        end_timestamp = int(date_end.timestamp()) if date_end else None

        while True:
            params: dict[str, str] = {
                "device_id": device_id,
                "scale": scale,
                "type": ",".join(measure_types),
            }
            if module_id:
                params["module_id"] = module_id
            if current_begin:
                params["date_begin"] = str(current_begin)
            if end_timestamp:
                params["date_end"] = str(end_timestamp)

            data = await self._api_request("getmeasure", params=params)
            response = MeasureResponse.model_validate(data)

            if not response.body:
                break

            # Track the latest timestamp we've seen for pagination
            latest_timestamp = 0
            batch_count = 0

            for batch in response.body:
                timestamps = batch.timestamps()
                for idx, values in enumerate(batch.value):
                    ts = timestamps[idx]
                    latest_timestamp = max(latest_timestamp, ts)
                    batch_count += 1

                    timestamp = datetime.fromtimestamp(ts, tz=UTC)
                    for i, measure_type in enumerate(measure_types):
                        if i < len(values) and values[i] is not None:
                            result[measure_type].append((timestamp, values[i]))

            # If we got fewer than 1024 points, we're done
            # Otherwise, continue from the last timestamp + 1
            if batch_count < 1024:
                break

            current_begin = latest_timestamp + 1
            if end_timestamp and current_begin >= end_timestamp:
                break

            logger.info(
                "Paginating getmeasure request",
                batch_count=batch_count,
                next_begin=current_begin,
            )

        return result

    ###################
    # Context manager #
    ###################

    async def __aenter__(self) -> Self:
        if not self.client:
            self.client = httpx.AsyncClient()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    ####################
    # Internal helpers #
    ####################

    async def _api_request(
        self, endpoint: str, *, params: dict[str, str] | None = None
    ) -> Any:
        """
        Make an authenticated API request.
        """
        if not self.client:
            self.client = httpx.AsyncClient()

        if not self.access_token:
            raise NetatmoAPIError("No access token available")

        response = await self.client.get(
            f"{API_URL}/{endpoint}",
            params=params or {},
            headers={"Authorization": f"Bearer {self.access_token}"},
        )

        if response.status_code == 403:
            error_data = response.json()
            error = error_data.get("error", {})
            if isinstance(error, dict) and error.get("code") == 3:
                raise ExpiredAccessToken("Access token has expired")
            raise NetatmoAPIError(f"API request forbidden: {error}")

        if response.status_code == 401:
            raise ExpiredAccessToken("Access token has expired")

        response.raise_for_status()
        return response.json()


def getenv(key: str) -> str:
    if value := os.getenv(key):
        return value

    raise KeyError(f"Environment variable {key} not set")
