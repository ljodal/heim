from datetime import UTC, datetime, timedelta

import structlog

from ...sensors.queries import save_measurements
from ...sensors.types import Attribute
from ...tasks import task
from .client import NetatmoClient
from .queries import get_netatmo_sensor
from .services import with_netatmo_client

logger = structlog.get_logger()

# Mapping from Netatmo module type to the data types it provides
# and how to map them to our Attribute enum
MODULE_TYPE_ATTRIBUTES: dict[str, dict[str, Attribute]] = {
    "NAMain": {
        "Temperature": Attribute.AIR_TEMPERATURE,
        "Humidity": Attribute.HUMIDITY,
        "Pressure": Attribute.AIR_PRESSURE,
        "CO2": Attribute.CO2,
        "Noise": Attribute.NOISE,
    },
    "NAModule1": {
        "Temperature": Attribute.AIR_TEMPERATURE,
        "Humidity": Attribute.HUMIDITY,
    },
    "NAModule2": {
        # Wind gauge - we don't have wind attributes yet, skip for now
    },
    "NAModule3": {
        # Rain gauge - we could use precipitation amount
        "Rain": Attribute.PRECIPITATION_AMOUNT,
    },
    "NAModule4": {
        "Temperature": Attribute.AIR_TEMPERATURE,
        "Humidity": Attribute.HUMIDITY,
        "CO2": Attribute.CO2,
    },
}


@task(name="update-netatmo-sensor-data", allow_skip=True, atomic=False)
@with_netatmo_client
async def update_sensor_data(
    client: NetatmoClient,
    *,
    account_id: int,
    sensor_id: int,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
) -> None:
    """
    Load and save measurements for the given Netatmo sensor.

    For Netatmo we use the getstationsdata endpoint to get current readings,
    and getmeasure endpoint for historical data.
    """

    netatmo_id, station_id, module_type, last_update_time = await get_netatmo_sensor(
        account_id=account_id, sensor_id=sensor_id
    )

    attribute_mapping = MODULE_TYPE_ATTRIBUTES.get(module_type, {})
    if not attribute_mapping:
        logger.warning(
            "No attribute mapping for module type",
            module_type=module_type,
            sensor_id=sensor_id,
        )
        return

    # Determine the time range to fetch
    if from_time is None:
        # Default to fetching from the last update or 7 days back
        from_time = last_update_time or datetime.now(UTC) - timedelta(days=7)

    if to_time is None:
        to_time = datetime.now(UTC)

    logger.info(
        "Starting Netatmo sensor data fetch",
        sensor_id=sensor_id,
        netatmo_id=netatmo_id,
        module_type=module_type,
        from_time=from_time.isoformat(),
        to_time=to_time.isoformat(),
    )

    # Determine module_id parameter (None for main station, module ID for others)
    module_id = netatmo_id if module_type != "NAMain" else None

    # Fetch historical measurements using getmeasure
    measure_types = list(attribute_mapping.keys())

    try:
        measurements = await client.get_measure(
            device_id=station_id,
            module_id=module_id,
            scale="max",  # Maximum resolution
            measure_types=measure_types,
            date_begin=from_time,
            date_end=to_time,
        )
    except Exception as e:
        logger.error(
            "Failed to fetch measurements",
            sensor_id=sensor_id,
            error=str(e),
        )
        raise

    # Convert to our measurement format and save
    total_measurements = 0
    values: list[tuple[Attribute, datetime, float]] = []

    for measure_type, data_points in measurements.items():
        attribute = attribute_mapping.get(measure_type)
        if attribute is None:
            continue

        for timestamp, value in data_points:
            if value is not None:
                # Convert value based on attribute type to match Aqara format:
                # Temperature: Netatmo gives 23.4°C, store as 2340 (×100)
                # Humidity: Netatmo gives 45%, store as 4500 (×100)
                # Pressure: Netatmo gives 1019.2 mbar, store as 101920 (×100)
                # CO2: Netatmo gives 650 ppm, store as-is
                # Noise: Netatmo gives 32 dB, store as-is
                if attribute in (
                    Attribute.AIR_TEMPERATURE,
                    Attribute.HUMIDITY,
                    Attribute.AIR_PRESSURE,
                ):
                    float_value = value * 100
                else:
                    float_value = value

                values.append((attribute, timestamp, float_value))
                total_measurements += 1

    if values:
        await save_measurements(sensor_id=sensor_id, values=values)

    logger.info(
        "Finished Netatmo sensor data fetch",
        sensor_id=sensor_id,
        total_measurements=total_measurements,
    )
