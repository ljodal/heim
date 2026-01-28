from datetime import datetime

from pydantic import BaseModel


class TemperatureReading(BaseModel):
    date: datetime
    temperature: float


class ForecastInstance(BaseModel):
    created_at: datetime
    age_hours: float
    data: list[TemperatureReading]


class TemperatureChartData(BaseModel):
    location_name: str
    current_temperature: float | None
    last_updated: datetime | None
    history: list[TemperatureReading]
    forecasts: list[ForecastInstance]
    now: datetime
