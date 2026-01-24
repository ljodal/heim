from datetime import datetime
from typing import Any, Generic, Literal, NotRequired, TypedDict, TypeVar, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


class QueryResourceInfoData(TypedDict):
    model: str


class FetchResourceHistoryData(TypedDict):
    subjectId: str
    resourceIds: list[str]
    startTime: str
    scanId: str | None
    endTime: NotRequired[str]
    size: NotRequired[int]


Intent = Union[
    Literal["config.auth.getAuthCode"],
    Literal["config.auth.getToken"],
    Literal["config.auth.refreshToken"],
    Literal["query.device.info"],
    Literal["query.resource.info"],
    Literal["fetch.resource.history"],
]

IntentData = Union[
    GetAuthCodeData,
    GetTokenData,
    RefreshTokenData,
    QueryDeviceInfoData,
    QueryResourceInfoData,
    FetchResourceHistoryData,
]


##################
# Response types #
##################

T = TypeVar("T")


class BaseResponse(BaseModel, Generic[T]):
    code: int
    message: str
    msg_details: str | None = None
    request_id: str

    # If we do not get a successful response this is not set, so we need to
    # have a default value here.
    result: T | None = None

    @field_validator("result", mode="before")
    def result_ignore_empty_string(cls, v: Any) -> Any:
        return None if v == "" else v

    model_config = ConfigDict(alias_generator=to_camel)


class AuthCodeResult(BaseModel):
    auth_code: str | None = None
    model_config = ConfigDict(alias_generator=to_camel)


class AccessTokenResult(BaseModel):
    expires_in: int
    access_token: str
    refresh_token: str
    model_config = ConfigDict(alias_generator=to_camel)


class RefreshTokenResult(BaseModel):
    expires_in: int
    access_token: str
    refresh_token: str
    model_config = ConfigDict(alias_generator=to_camel)


class DeviceInfo(BaseModel, protected_namespaces=()):
    parent_did: str | None = None
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
    model_config = ConfigDict(alias_generator=to_camel)


class QueryDeviceInfoResult(BaseModel):
    data: list[DeviceInfo]
    total_count: int
    model_config = ConfigDict(alias_generator=to_camel)


class ResourceInfo(BaseModel):
    enums: str | None = None
    resource_id: str
    min_value: int | None = None
    unit: int
    access: int | None = None
    max_value: int | None = None
    default_value: str | None = None
    name: str
    description: str
    model: str
    model_config = ConfigDict(alias_generator=to_camel)


class ResourceHistoryPoint(BaseModel):
    timestamp: datetime = Field(alias="timeStamp")
    resource_id: str
    value: int
    subject_id: str
    model_config = ConfigDict(alias_generator=to_camel)


class QueryResourceHistoryResult(BaseModel):
    data: list[ResourceHistoryPoint]
    scan_id: str | None = None
    model_config = ConfigDict(alias_generator=to_camel)
