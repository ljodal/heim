from datetime import datetime, timedelta, timezone

from ...sensors.queries import save_measurements
from ...sensors.types import Attribute
from ...tasks import task
from .client import AqaraClient
from .queries import get_aqara_sensor
from .services import with_aqara_client
from .types import QueryResourceHistoryResult

MODEL_TO_RESOURCE_MAPPING: dict[str, dict[str, Attribute]] = {
    "lumi.airmonitor.acn01": {
        "0.1.85": Attribute.AIR_TEMPERATURE,
        "0.2.85": Attribute.HUMIDITY,
        # "0.3.85": Attribute.AIR_QUALITY,
    },
    "lumi.plug.maeu01": {
        "0.1.85": Attribute.AIR_TEMPERATURE,
        "0.2.85": Attribute.HUMIDITY,
        "0.3.85": Attribute.AIR_PRESSURE,
    },
    "lumi.weather.v1": {
        "0.12.85": Attribute.POWER,
        "0.13.85": Attribute.ENERGY,
        "4.1.85": Attribute.POWER_STATE,
    },
}


@task(name="fetch-aqara-sensor-data")
@with_aqara_client
async def update_sensor_data(
    client: AqaraClient, *, account_id: int, sensor_id: int
) -> None:
    """
    Load and save measurements for the given sensor.
    """

    aqara_id, model, last_update_time = await get_aqara_sensor(
        account_id=account_id, sensor_id=sensor_id
    )

    # Accoring to the Aqara documentation historical data is available 7 days
    # back, so we default to loading as far back as we can if we have no
    # previous data for the sensor.
    if last_update_time is None:
        last_update_time = datetime.now(timezone.utc) - timedelta(days=7)

    resource_mapping = MODEL_TO_RESOURCE_MAPPING[model]

    # Loop and load measurements until we don't get any new data
    result: QueryResourceHistoryResult | None = None
    while True:
        result = await client.get_resource_history(
            device_id=aqara_id,
            resource_ids=resource_mapping,
            from_time=last_update_time,
            scan_id=result.scan_id if result else None,
        )
        if not result.data:
            break

        await save_measurements(
            sensor_id=sensor_id,
            values=(
                (
                    resource_mapping[measurement.resource_id],
                    measurement.timestamp,
                    measurement.value,
                )
                for measurement in result.data
            ),
        )
