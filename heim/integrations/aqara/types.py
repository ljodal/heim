from datetime import datetime
from typing import Generic, Literal, Optional, TypedDict, TypeVar, Union

from pydantic import BaseModel, Field
from pydantic.generics import GenericModel

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
    scanId: Optional[str]


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


class BaseResponse(GenericModel, Generic[T]):
    code: int
    message: str
    msg_details: Optional[str] = None
    request_id: str

    # If we do not get a successful response this is not set, so we need to
    # have a default value here.
    result: Optional[T] = None

    class Config:
        alias_generator = to_camel


class AuthCodeResult(BaseModel):
    auth_code: Optional[str]

    class Config:
        alias_generator = to_camel


class AccessTokenResult(BaseModel):
    expires_in: int
    access_token: str
    refresh_token: str

    class Config:
        alias_generator = to_camel


class RefreshTokenResult(BaseModel):
    expires_in: int
    access_token: str
    refresh_token: str

    class Config:
        alias_generator = to_camel


class DeviceInfo(BaseModel):
    parent_did: Optional[str]
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


class QueryDeviceInfoResult(BaseModel):
    data: list[DeviceInfo]
    total_count: int

    class Config:
        alias_generator = to_camel


class ResourceInfo(BaseModel):
    enums: Optional[str]
    resource_id: str
    min_value: Optional[int]
    unit: int
    access: Optional[int]
    max_value: Optional[int]
    default_value: Optional[str]
    name: str
    description: str
    model: str

    class Config:
        alias_generator = to_camel


class ResourceHistoryPoint(BaseModel):
    timestamp: datetime = Field(alias="timeStamp")
    resource_id: str
    value: int
    subject_id: str

    class Config:
        alias_generator = to_camel


class QueryResourceHistoryResult(BaseModel):

    data: list[ResourceHistoryPoint]
    scan_id: Optional[str]

    class Config:
        alias_generator = to_camel
