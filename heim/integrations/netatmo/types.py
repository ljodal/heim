from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    result = []
    for i, char in enumerate(name):
        if char.isupper() and i > 0:
            result.append("_")
        result.append(char.lower())
    return "".join(result)


class TokenResponse(BaseModel):
    """Response from OAuth token endpoint."""

    access_token: str
    refresh_token: str
    expires_in: int
    scope: list[str] | None = None

    @field_validator("scope", mode="before")
    @classmethod
    def parse_scope(cls, v: Any) -> list[str] | None:
        if isinstance(v, str):
            return v.split() if v else None
        return v


class DashboardData(BaseModel):
    """Sensor readings from a module's dashboard."""

    time_utc: datetime | None = Field(default=None, alias="time_utc")

    # Common measurements
    temperature: float | None = Field(default=None, alias="Temperature")
    humidity: int | None = Field(default=None, alias="Humidity")
    pressure: float | None = Field(default=None, alias="Pressure")
    absolute_pressure: float | None = Field(default=None, alias="AbsolutePressure")

    # Indoor-specific
    co2: int | None = Field(default=None, alias="CO2")
    noise: int | None = Field(default=None, alias="Noise")

    # Temperature extremes
    min_temp: float | None = None
    max_temp: float | None = None
    date_min_temp: datetime | None = None
    date_max_temp: datetime | None = None

    # Trends
    temp_trend: str | None = None
    pressure_trend: str | None = None

    # Rain gauge (NAModule3)
    rain: float | None = Field(default=None, alias="Rain")
    sum_rain_1: float | None = None
    sum_rain_24: float | None = None

    # Wind gauge (NAModule2)
    wind_strength: int | None = Field(default=None, alias="WindStrength")
    wind_angle: int | None = Field(default=None, alias="WindAngle")
    gust_strength: int | None = Field(default=None, alias="GustStrength")
    gust_angle: int | None = Field(default=None, alias="GustAngle")

    model_config = ConfigDict(populate_by_name=True)


class Module(BaseModel):
    """A Netatmo module (outdoor sensor, indoor sensor, etc.)."""

    id: str = Field(alias="_id")
    type: str
    module_name: str
    data_type: list[str]
    dashboard_data: DashboardData | None = None

    # Battery and signal
    battery_percent: int | None = None
    battery_vp: int | None = None
    rf_status: int | None = None

    # Timestamps
    last_message: datetime | None = None
    last_seen: datetime | None = None
    last_setup: datetime | None = None

    # Firmware
    firmware: int | None = None

    model_config = ConfigDict(populate_by_name=True)


class Station(BaseModel):
    """A Netatmo weather station (the main indoor unit)."""

    id: str = Field(alias="_id")
    type: str = "NAMain"
    station_name: str
    home_name: str
    module_name: str
    data_type: list[str]
    dashboard_data: DashboardData | None = None
    modules: list[Module] = Field(default_factory=list)

    # WiFi signal
    wifi_status: int | None = None

    # Timestamps
    last_status_store: datetime | None = None
    last_upgrade: datetime | None = None

    # Location
    place: dict[str, Any] | None = None

    # Firmware
    firmware: int | None = None

    model_config = ConfigDict(populate_by_name=True)


class StationsDataResponse(BaseModel):
    """Response from /api/getstationsdata endpoint."""

    devices: list[Station]
    user: dict[str, Any] | None = None


class MeasureValue(BaseModel):
    """A single measurement point from getmeasure endpoint."""

    timestamp: datetime
    value: float


class GetMeasureResponse(BaseModel):
    """Response from /api/getmeasure endpoint."""

    body: dict[str, list[list[float | None]]]
    status: str
    time_exec: float | None = None
    time_server: datetime | None = None
