from datetime import datetime
from decimal import Decimal
from typing import Optional

import pydantic


class ForecastDetailsInstant(pydantic.BaseModel):
    air_pressure_at_sea_level: Optional[Decimal]
    air_temperature: Optional[Decimal]
    cloud_area_fraction: Optional[Decimal]
    cloud_area_fraction_high: Optional[Decimal]
    cloud_area_fraction_low: Optional[Decimal]
    cloud_area_fraction_medium: Optional[Decimal]
    dew_point_temperature: Optional[Decimal]
    fog_area_fraction: Optional[Decimal]
    relative_humidity: Optional[Decimal]
    wind_from_direction: Optional[Decimal]
    wind_speed: Optional[Decimal]
    wind_speed_of_gust: Optional[Decimal]


class ForecastDataInstant(pydantic.BaseModel):
    details: ForecastDetailsInstant


class ForecastDetailsPeriod(pydantic.BaseModel):
    air_temperature_max: Optional[Decimal]
    air_temperature_min: Optional[Decimal]
    precipitation_amount: Optional[Decimal]
    precipitation_amount_max: Optional[Decimal]
    precipitation_amount_min: Optional[Decimal]
    probability_of_precipitation: Optional[Decimal]
    probability_of_thunder: Optional[Decimal]
    ultraviolet_index_clear_sky_max: Optional[Decimal]


class ForecastDataPeriod(pydantic.BaseModel):
    details: ForecastDetailsPeriod


class ForecastData(pydantic.BaseModel):
    instant: ForecastDataInstant
    next_1_hour: Optional[ForecastDataPeriod]
    next_6_hours: Optional[ForecastDataPeriod]
    next_12_hours: Optional[ForecastDataPeriod]


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
