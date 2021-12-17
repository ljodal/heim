from datetime import datetime
from typing import Literal, Optional, TypedDict, Union

import pydantic

###########
# Helpers #
###########


def to_camel(name: str) -> str:
    first, *rest = name.split("_")
    return f"{first}{''.join(word.capitalize() for word in rest)}"


################
# Intent types #
################


class GetAuthCodeData(TypedDict):
    account: str
    accountType: int
    accessTokenValidity: str


class GetTokenData(TypedDict):
    authCode: str
    account: str
    accountType: int


class RefreshTokenData(TypedDict):
    refreshToken: str


class QueryDeviceInfoData(TypedDict, total=False):
    dids: list[str]
    positionId: str
    pageNum: int
    pageSize: int


class FetchResourceHistoryData(TypedDict):
    subjectId: str
    resourceIds: list[str]
    startTime: str


Intent = Union[
    Literal["config.auth.getAuthCode"],
    Literal["config.auth.getToken"],
    Literal["config.auth.refreshToken"],
    Literal["query.device.info"],
    Literal["fetch.resource.history"],
]

IntentData = Union[
    GetAuthCodeData,
    GetTokenData,
    RefreshTokenData,
    QueryDeviceInfoData,
    FetchResourceHistoryData,
]


##################
# Response types #
##################


class GetAuthCodeResponse(pydantic.BaseModel):
    auth_code: Optional[str]

    class Config:
        alias_generator = to_camel


class GetTokenResponse(pydantic.BaseModel):
    expires_in: int
    access_token: str
    refresh_token: str

    class Config:
        alias_generator = to_camel


class RefreshTokenResponse(pydantic.BaseModel):
    expires_in: int
    access_token: str
    refresh_token: str

    class Config:
        alias_generator = to_camel


class DeviceInfo(pydantic.BaseModel):
    parent_id: Optional[str]
    position_id: str
    create_time: datetime
    update_time: datetime
    time_zone: str
    model: str
    model_type: int
    state: int
    firmware_version: str
    device_name: str
    did: str

    class Config:
        alias_generator = to_camel


class QueryDeviceInfoResponse(pydantic.BaseModel):
    data: list[DeviceInfo]
    total_count: int

    class Config:
        alias_generator = to_camel


class ResourceHistoryPoint(pydantic.BaseModel):
    time_stamp: datetime
    resource_id: str
    value: str
    subject_id: str

    class Config:
        alias_generator = to_camel


class QueryResourceHistoryResponse(pydantic.BaseModel):

    data: list[ResourceHistoryPoint]
    scan_id: Optional[str]

    class Config:
        alias_generator = to_camel
