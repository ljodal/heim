import hashlib
import string
import time
from collections.abc import Iterable
from datetime import datetime
from typing import Any, Self, TypeVar

import httpx

from ...accounts.utils import get_random_string
from ..common import getenv
from .exceptions import AqaraAPIError, ExpiredAccessToken
from .types import (
    AccessTokenResult,
    AuthCodeResult,
    BaseResponse,
    DeviceInfo,
    FetchResourceHistoryData,
    Intent,
    IntentData,
    QueryDeviceInfoResult,
    QueryResourceHistoryResult,
    RefreshTokenResult,
    ResourceInfo,
)


class AqaraClient:
    """
    A client for communicating with the Aqara Open API.
    """

    def __init__(self, *, access_token: str | None = None) -> None:
        self.app_id = getenv("AQARA_APP_ID")
        self.app_key = getenv("AQARA_APP_KEY")
        self.key_id = getenv("AQARA_KEY_ID")
        self.domain = getenv("AQARA_DOMAIN")
        self.access_token = access_token
        self.client: httpx.AsyncClient | None = None

    async def close(self) -> None:
        if self.client:
            await self.client.aclose()
            self.client = None

    ########
    # Auth #
    ########

    async def get_auth_code(self, *, account: str) -> AuthCodeResult:
        return await self._request(
            intent="config.auth.getAuthCode",
            data={"account": account, "accountType": 0, "accessTokenValidity": "1h"},
            response_type=BaseResponse[AuthCodeResult],
        )

    async def get_token(self, *, code: str, account: str) -> AccessTokenResult:
        return await self._request(
            intent="config.auth.getToken",
            data={"authCode": code, "account": account, "accountType": 0},
            response_type=BaseResponse[AccessTokenResult],
        )

    async def refresh_token(self, *, refresh_token: str) -> RefreshTokenResult:
        return await self._request(
            intent="config.auth.refreshToken",
            data={"refreshToken": refresh_token},
            response_type=BaseResponse[RefreshTokenResult],
        )

    ###############
    # Device info #
    ###############

    async def get_all_devices(self) -> list[DeviceInfo]:
        """
        Get all devices registered on the account
        """

        devices = []

        page_num = 1
        while True:
            result = await self._request(
                intent="query.device.info",
                data={"pageNum": page_num},
                response_type=BaseResponse[QueryDeviceInfoResult],
            )
            devices.extend(result.data)

            if result.total_count <= len(devices):
                break

            page_num += 1

        return devices

    async def get_device_resources(self, *, model: str) -> list[ResourceInfo]:
        """
        Get all resources for the given device model.
        """

        return await self._request(
            intent="query.resource.info",
            data={"model": model},
            response_type=BaseResponse[list[ResourceInfo]],
        )

    ################
    # Measurements #
    ################

    async def get_resource_history(
        self,
        *,
        device_id: str,
        resource_ids: Iterable[str],
        from_time: datetime,
        to_time: datetime | None = None,
        scan_id: str | None = None,
    ) -> QueryResourceHistoryResult:
        data: FetchResourceHistoryData = {
            "subjectId": device_id,
            "resourceIds": list(resource_ids),
            "startTime": str(int(from_time.timestamp() * 1000)),
            "size": 300,
            "scanId": scan_id,
        }
        if to_time:
            data["endTime"] = str(int(to_time.timestamp() * 1000))

        return await self._request(
            intent="fetch.resource.history",
            data=data,
            response_type=BaseResponse[QueryResourceHistoryResult],
        )

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

    T = TypeVar("T")

    async def _request(
        self, intent: Intent, data: IntentData, response_type: type[BaseResponse[T]]
    ) -> T:
        if not self.client:
            self.client = httpx.AsyncClient()

        request = self.client.build_request(
            "POST",
            f"https://{self.domain}/v3.0/open/api",
            json={"intent": intent, "data": data},
        )
        self._prepare_auth(request)

        response = await self.client.send(request)
        return self._check_response(response, response_type)

    def _prepare_auth(self, request: httpx.Request) -> None:
        timestamp = str(int(time.time() * 1000))
        nonce = get_nonce(24)

        value = f"accesstoken={self.access_token}&" if self.access_token else ""
        value += (
            f"appid={self.app_id}&"
            f"keyid={self.key_id}&"
            f"nonce={nonce}&"
            f"time={timestamp}"
            f"{self.app_key}"
        )
        signature = hashlib.md5(value.lower().encode()).hexdigest()

        if self.access_token:
            request.headers["Accesstoken"] = self.access_token
        request.headers["Appid"] = self.app_id
        request.headers["Keyid"] = self.key_id
        request.headers["Time"] = timestamp
        request.headers["Nonce"] = nonce
        request.headers["Sign"] = signature

    def _check_response(
        self, response: httpx.Response, response_type: type[BaseResponse[T]]
    ) -> T:
        response.raise_for_status()

        parsed_response = response_type.model_validate_json(response.text)

        if parsed_response.code == 108:
            raise ExpiredAccessToken("Access token has expired", parsed_response)
        elif parsed_response.code != 0:
            raise AqaraAPIError(
                f"Unexpected response from Aqara API: {parsed_response.code}",
                parsed_response,
            )
        elif parsed_response.result is None:
            # TODO: Might need allow this if T is Optional / None
            raise AqaraAPIError("No result in response", parsed_response)

        return parsed_response.result


def get_nonce(length: int) -> str:
    return get_random_string(
        length, allowed_chars=string.ascii_lowercase + string.digits
    )
