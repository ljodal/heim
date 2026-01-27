from datetime import UTC, datetime, timedelta

import structlog

from ...sensors.queries import save_measurements
from ...sensors.types import Attribute
from ...tasks import task
from .client import EaseeClient
from .queries import get_easee_charger

logger = structlog.get_logger()


@task(name="update-easee-charger-state", allow_skip=True, atomic=False)
@EaseeClient.authenticated()
async def update_charger_state(
    client: EaseeClient,
    *,
    account_id: int,
    sensor_id: int,
) -> None:
    """
    Fetch and save the current state of an Easee charger.

    This captures a snapshot of power, current, voltage, and energy usage.
    """

    charger_id, _ = await get_easee_charger(account_id=account_id, sensor_id=sensor_id)

    logger.info(
        "Fetching Easee charger state",
        sensor_id=sensor_id,
        charger_id=charger_id,
    )

    state = await client.get_charger_state(charger_id)
    now = datetime.now(UTC)

    values: list[tuple[Attribute, datetime, float]] = []

    # Power in watts (API returns kW)
    if state.total_power is not None:
        values.append((Attribute.POWER, now, state.total_power * 1000))

    # Session energy in Wh (API returns kWh)
    if state.session_energy is not None:
        values.append((Attribute.ENERGY, now, state.session_energy * 1000))

    # Output current in milliamps (API returns amps)
    if state.output_current is not None:
        values.append((Attribute.CURRENT, now, state.output_current * 1000))

    # Average voltage in millivolts (API returns volts)
    # We take the average of available phase voltages
    voltages = [
        v
        for v in [
            state.in_voltage_t1_t2,
            state.in_voltage_t2_t3,
            state.in_voltage_t3_t4,
        ]
        if v is not None
    ]
    if voltages:
        avg_voltage = sum(voltages) / len(voltages)
        values.append((Attribute.VOLTAGE, now, avg_voltage * 1000))

    if values:
        await save_measurements(sensor_id=sensor_id, values=values)

    logger.info(
        "Saved Easee charger state",
        sensor_id=sensor_id,
        charger_id=charger_id,
        measurements=len(values),
        power_kw=state.total_power,
        session_energy_kwh=state.session_energy,
    )


@task(name="update-easee-hourly-usage", allow_skip=True, atomic=False)
@EaseeClient.authenticated()
async def update_hourly_usage(
    client: EaseeClient,
    *,
    account_id: int,
    sensor_id: int,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
) -> None:
    """
    Fetch and save hourly energy usage for an Easee charger.

    This provides historical energy consumption data.
    """

    charger_id, last_update_time = await get_easee_charger(
        account_id=account_id, sensor_id=sensor_id
    )

    # Default to fetching from last update or 7 days back
    if from_time is None:
        from_time = last_update_time or datetime.now(UTC) - timedelta(days=7)

    if to_time is None:
        to_time = datetime.now(UTC)

    logger.info(
        "Fetching Easee hourly usage",
        sensor_id=sensor_id,
        charger_id=charger_id,
        from_time=from_time.isoformat(),
        to_time=to_time.isoformat(),
    )

    hourly_data = await client.get_hourly_usage(
        charger_id,
        from_date=from_time,
        to_date=to_time,
    )

    values: list[tuple[Attribute, datetime, float]] = []
    for usage in hourly_data:
        # Energy in Wh (API returns kWh)
        values.append((Attribute.ENERGY, usage.date, usage.energy_used * 1000))

    if values:
        await save_measurements(sensor_id=sensor_id, values=values)

    logger.info(
        "Saved Easee hourly usage",
        sensor_id=sensor_id,
        charger_id=charger_id,
        measurements=len(values),
    )
