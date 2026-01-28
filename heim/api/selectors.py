from datetime import UTC, datetime

from ..accounts.queries import get_location
from ..forecasts.queries import get_forecast, get_instances
from ..sensors.queries import get_measurements_averaged, get_sensors
from ..sensors.types import Attribute
from .models import ForecastInstance, TemperatureChartData, TemperatureReading


async def get_temperature_chart_data(
    *, account_id: int, location_id: int
) -> TemperatureChartData | None:
    """
    Get temperature chart data for a location.

    Uses the first outdoor sensor for the location.
    Returns 48 hours of historical temperature readings (15-minute buckets)
    and up to 3 forecast instances (latest, 12h old, 24h old).

    Returns None if the location doesn't exist or has no outdoor sensors.
    """
    # Get location info
    location = await get_location(account_id=account_id, location_id=location_id)
    if not location:
        return None

    location_name = location.name

    # Get first outdoor sensor
    outdoor_sensors = await get_sensors(
        account_id=account_id, location_id=location_id, is_outdoor=True
    )
    if not outdoor_sensors:
        return None

    sensor_id = outdoor_sensors[0][0]

    # Get 48 hours of averaged measurements
    measurements = await get_measurements_averaged(
        sensor_id=sensor_id,
        attribute=Attribute.AIR_TEMPERATURE,
        hours=48,
        bucket_minutes=15,
    )

    # Convert to response format (centidegrees -> Celsius)
    history = [
        TemperatureReading(date=ts, temperature=value / 100)
        for ts, value in measurements
    ]

    # Current temperature is the latest measurement
    current_temperature: float | None = None
    last_updated: datetime | None = None
    if history:
        current_temperature = history[-1].temperature
        last_updated = history[-1].date

    # Get forecast instances
    now = datetime.now(UTC)
    forecasts: list[ForecastInstance] = []

    forecast_id = await get_forecast(account_id=account_id, location_id=location_id)
    if forecast_id:
        instances = await get_instances(
            forecast_id=forecast_id, attribute=Attribute.AIR_TEMPERATURE
        )
        for created_at, values in instances.items():
            age_hours = (now - created_at).total_seconds() / 3600
            # Filter to future values only
            future_values = [(ts, val) for ts, val in values if ts > now]
            if future_values:
                forecasts.append(
                    ForecastInstance(
                        created_at=created_at,
                        age_hours=age_hours,
                        data=[
                            TemperatureReading(date=ts, temperature=val / 100)
                            for ts, val in future_values
                        ],
                    )
                )

    # Sort forecasts by age (newest first)
    forecasts.sort(key=lambda f: f.age_hours)

    return TemperatureChartData(
        location_name=location_name or "Unknown",
        current_temperature=current_temperature,
        last_updated=last_updated,
        history=history,
        forecasts=forecasts,
        now=now,
    )
