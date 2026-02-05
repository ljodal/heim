from datetime import datetime
from decimal import Decimal
from typing import Literal

import pydantic


class ForecastDetailsInstant(pydantic.BaseModel):
    air_pressure_at_sea_level: Decimal | None = None
    air_temperature: Decimal | None = None
    cloud_area_fraction: Decimal | None = None
    cloud_area_fraction_high: Decimal | None = None
    cloud_area_fraction_low: Decimal | None = None
    cloud_area_fraction_medium: Decimal | None = None
    dew_point_temperature: Decimal | None = None
    fog_area_fraction: Decimal | None = None
    relative_humidity: Decimal | None = None
    wind_from_direction: Decimal | None = None
    wind_speed: Decimal | None = None
    wind_speed_of_gust: Decimal | None = None


class ForecastDataInstant(pydantic.BaseModel):
    details: ForecastDetailsInstant


class ForecastDetailsPeriod(pydantic.BaseModel):
    air_temperature_max: Decimal | None = None
    air_temperature_min: Decimal | None = None
    precipitation_amount: Decimal | None = None
    precipitation_amount_max: Decimal | None = None
    precipitation_amount_min: Decimal | None = None
    probability_of_precipitation: Decimal | None = None
    probability_of_thunder: Decimal | None = None
    ultraviolet_index_clear_sky_max: Decimal | None = None


class ForecastSummary(pydantic.BaseModel):
    symbol_code: str


class ForecastDataPeriod(pydantic.BaseModel):
    summary: ForecastSummary
    details: ForecastDetailsPeriod


class ForecastData(pydantic.BaseModel):
    instant: ForecastDataInstant
    next_1_hours: ForecastDataPeriod | None = None
    next_6_hours: ForecastDataPeriod | None = None
    next_12_hours: ForecastDataPeriod | None = None


class ForecastTimeStep(pydantic.BaseModel):
    time: datetime
    data: ForecastData


class ForecastUnits(pydantic.BaseModel):
    air_pressure_at_sea_level: str | None = None
    air_temperature: str | None = None
    air_temperature_max: str | None = None
    air_temperature_min: str | None = None
    cloud_area_fraction: str | None = None
    cloud_area_fraction_high: str | None = None
    cloud_area_fraction_low: str | None = None
    cloud_area_fraction_medium: str | None = None
    dew_point_temperature: str | None = None
    fog_area_fraction: str | None = None
    precipitation_amount: str | None = None
    precipitation_amount_max: str | None = None
    precipitation_amount_min: str | None = None
    probability_of_precipitation: str | None = None
    probability_of_thunder: str | None = None
    relative_humidity: str | None = None
    ultraviolet_index_clear_sky_max: str | None = None
    wind_from_direction: str | None = None
    wind_speed: str | None = None
    wind_speed_of_gust: str | None = None


class ForecastMeta(pydantic.BaseModel):
    updated_at: datetime
    units: ForecastUnits | None = None


class ForecastProperties(pydantic.BaseModel):
    meta: ForecastMeta
    timeseries: list[ForecastTimeStep]


class PointGeometry(pydantic.BaseModel):
    type: Literal["Point"]
    coordinates: list[float]


class ForecastResponse(pydantic.BaseModel):
    type: Literal["Feature"]
    geometry: PointGeometry
    properties: ForecastProperties
