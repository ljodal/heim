from datetime import datetime
from decimal import Decimal
from typing import Optional

import pydantic


class ForecastDetailsInstant(pydantic.BaseModel):
    air_pressure_at_sea_level: Optional[Decimal] = None
    air_temperature: Optional[Decimal] = None
    cloud_area_fraction: Optional[Decimal] = None
    cloud_area_fraction_high: Optional[Decimal] = None
    cloud_area_fraction_low: Optional[Decimal] = None
    cloud_area_fraction_medium: Optional[Decimal] = None
    dew_point_temperature: Optional[Decimal] = None
    fog_area_fraction: Optional[Decimal] = None
    relative_humidity: Optional[Decimal] = None
    wind_from_direction: Optional[Decimal] = None
    wind_speed: Optional[Decimal] = None
    wind_speed_of_gust: Optional[Decimal] = None


class ForecastDataInstant(pydantic.BaseModel):
    details: ForecastDetailsInstant


class ForecastDetailsPeriod(pydantic.BaseModel):
    air_temperature_max: Optional[Decimal] = None
    air_temperature_min: Optional[Decimal] = None
    precipitation_amount: Optional[Decimal] = None
    precipitation_amount_max: Optional[Decimal] = None
    precipitation_amount_min: Optional[Decimal] = None
    probability_of_precipitation: Optional[Decimal] = None
    probability_of_thunder: Optional[Decimal] = None
    ultraviolet_index_clear_sky_max: Optional[Decimal] = None


class ForecastDataPeriod(pydantic.BaseModel):
    details: ForecastDetailsPeriod


class ForecastData(pydantic.BaseModel):
    instant: ForecastDataInstant
    next_1_hour: Optional[ForecastDataPeriod] = None
    next_6_hours: Optional[ForecastDataPeriod] = None
    next_12_hours: Optional[ForecastDataPeriod] = None


class ForecastTimeStep(pydantic.BaseModel):
    time: datetime
    data: ForecastData


class ForecastMeta(pydantic.BaseModel):
    updated_at: datetime


class ForecastProperties(pydantic.BaseModel):
    meta: ForecastMeta
    timeseries: list[ForecastTimeStep]


class ForecastResponse(pydantic.BaseModel):
    properties: ForecastProperties
