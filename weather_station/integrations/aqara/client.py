import hashlib
import os
import random
import string
import time
from datetime import datetime
from typing import Any

import httpx

from .exceptions import AqaraAPIError, ExpiredAccessToken
from .types import (
    DeviceInfo,
    GetAuthCodeResponse,
    GetTokenResponse,
    Intent,
    IntentData,
    QueryDeviceInfoResponse,
    QueryResourceHistoryResponse,
    RefreshTokenResponse,
    ResourceHistoryPoint,
)


class AqaraClient:
    """
    A client for communicating with the Aqara Open API.
    """

    def __init__(self, *, access_token: str | None, refresh_token: str | None) -> None:
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

    async def get_auth_code(self, *, code: str, account: str) -> GetAuthCodeResponse:

        result = await self._request(
            intent="config.auth.getAuthCode",
            data={"account": account, "accountType": 0, "accessTokenValidity": "1h"},
        )
        return GetAuthCodeResponse(**result)

    async def get_token(self, *, code: str, account: str) -> GetTokenResponse:

        result = await self._request(
            intent="config.auth.getToken",
            data={"authCode": code, "account": account, "accountType": 0},
        )
        return GetTokenResponse(**result)

    async def refresh_token(self, *, refresh_token: str) -> RefreshTokenResponse:

        result = await self._request(
            intent="config.auth.refreshToken",
            data={"refreshToken": refresh_token},
        )
        return RefreshTokenResponse(**result)

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
            )
            data = QueryDeviceInfoResponse(**result)
            devices.extend(data.data)

            if data.total_count <= len(devices):
                break

            page_num += 1

        return devices

    ################
    # Measurements #
    ################

    async def get_measurements(
        self, *, device_id: str, resource_ids: list[str], from_time: datetime
    ) -> list[ResourceHistoryPoint]:

        start_time = str(int(from_time.timestamp() * 1000))

        result = await self._request(
            intent="fetch.resource.history",
            data={
                "subjectId": device_id,
                "resourceIds": resource_ids,
                "startTime": start_time,
            },
        )
        data = QueryResourceHistoryResponse(**result)
        return data.data

    ###################
    # Context manager #
    ###################

    async def __aenter__(self) -> "AqaraClient":
        if not self.client:
            self.client = httpx.AsyncClient()
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    ####################
    # Internal helpers #
    ####################

    async def _request(self, intent: Intent, data: IntentData) -> Any:

        if not self.client:
            self.client = httpx.AsyncClient()

        request = self.client.build_request(
            "POST",
            f"https://{self.domain}/v3.0/open/api",
            json={"intent": intent, "data": data},
        )
        self._prepare_auth(request)

        response = await self.client.send(request)
        return self._check_response(response)

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

    def _check_response(self, response: httpx.Response) -> dict:

        response.raise_for_status()
        data = response.json()

        print(data)

        assert isinstance(data, dict)
        assert "code" in data
        code = data["code"]
        if code == 108:
            raise ExpiredAccessToken
        elif code != 0:
            raise AqaraAPIError(f"Unexpected response from Aqara API: {code}")

        assert "result" in data
        assert isinstance(data["result"], dict)
        return data["result"]


def getenv(key: str) -> str:
    if value := os.getenv(key):
        return value

    raise KeyError(f"Environment variable {key} not set")


def get_nonce(length):
    letters = string.ascii_lowercase + string.digits
    return "".join(random.choice(letters) for i in range(length))
