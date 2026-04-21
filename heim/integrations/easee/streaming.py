"""
Easee charger real-time streaming via SignalR.

This module provides a streaming worker that maintains a persistent connection
to the Easee SignalR hub and receives real-time charger updates.
"""

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog

from ...sensors.queries import save_measurements
from ...sensors.types import Attribute
from .queries import get_easee_account, get_easee_chargers
from .signalr import SignalRClient

logger = structlog.get_logger()

# Easee SignalR hub URL
SIGNALR_HUB_URL = "https://streams.easee.com/hubs/chargers"


@dataclass
class ChargerObservation:
    """A single observation from the charger."""

    charger_id: str
    observation_id: int
    name: str
    value: Any
    timestamp: datetime


# Observation ID to Attribute mapping
# See: https://developer.easee.com/docs/observation-ids
OBSERVATION_MAPPING: dict[int, tuple[Attribute, float]] = {
    # Power observations
    120: (Attribute.POWER, 1000),  # totalPower (kW -> W)
    # Per-phase current observations (A -> mA)
    183: (Attribute.CURRENT_L1, 1000),  # inCurrentT2 (L1)
    184: (Attribute.CURRENT_L2, 1000),  # inCurrentT3 (L2)
    185: (Attribute.CURRENT_L3, 1000),  # inCurrentT4 (L3)
    # Per-phase voltage observations (V -> mV)
    193: (Attribute.VOLTAGE_L1, 1000),  # inVoltageT1T2 (L1)
    194: (Attribute.VOLTAGE_L2, 1000),  # inVoltageT2T3 (L2)
    195: (Attribute.VOLTAGE_L3, 1000),  # inVoltageT3T4 (L3)
    # Energy observations
    124: (Attribute.ENERGY, 1000),  # sessionEnergy (kWh -> Wh)
}


class EaseeStreamingWorker:
    """
    Worker that streams real-time data from Easee chargers.

    This maintains a SignalR connection and processes ProductUpdate events,
    storing measurements to the database.

    Usage:
        worker = EaseeStreamingWorker(account_id=1)
        await worker.run()
    """

    def __init__(
        self,
        account_id: int,
        *,
        on_observation: Callable[[int, ChargerObservation], Coroutine[Any, Any, None]]
        | None = None,
    ) -> None:
        self.account_id = account_id
        self._on_observation = on_observation
        self._charger_to_sensor: dict[str, int] = {}
        self._client: SignalRClient | None = None
        self._running = False

    async def run(self) -> None:
        """Run the streaming worker (blocking)."""
        self._running = True

        while self._running:
            try:
                await self._run_connection()
            except Exception:
                logger.exception("Streaming connection error, reconnecting...")
                await asyncio.sleep(5)

    async def stop(self) -> None:
        """Stop the streaming worker."""
        self._running = False
        if self._client:
            await self._client.close()

    async def _run_connection(self) -> None:
        """Establish connection and process messages."""
        # Get account credentials
        account = await get_easee_account(account_id=self.account_id)

        # Get registered chargers
        chargers = await get_easee_chargers(account_id=self.account_id)
        if not chargers:
            logger.warning("No chargers registered", account_id=self.account_id)
            return

        self._charger_to_sensor = {
            charger_id: sensor_id for sensor_id, _, charger_id in chargers
        }

        logger.info(
            "Starting Easee streaming",
            account_id=self.account_id,
            chargers=list(self._charger_to_sensor.keys()),
        )

        # Connect to SignalR
        self._client = SignalRClient(
            SIGNALR_HUB_URL,
            account.access_token,
        )

        try:
            await self._client.connect()

            # Subscribe to each charger
            for charger_id in self._charger_to_sensor:
                await self._client.send("SubscribeWithCurrentState", charger_id, True)
                logger.info("Subscribed to charger", charger_id=charger_id)

            # Process messages
            async for message in self._client.messages():
                if message.target == "ProductUpdate":
                    await self._handle_product_update(message.arguments)

        finally:
            await self._client.close()
            self._client = None

    async def _handle_product_update(self, arguments: list[Any]) -> None:
        """Handle a ProductUpdate message from SignalR."""
        if not arguments:
            return

        # ProductUpdate contains observation data
        # Format: [{"mid": "charger_id", "dataType": 1, "id": 120, "value": "1.5", ...}]
        for obs_data in arguments:
            try:
                charger_id = obs_data.get("mid") or obs_data.get("chargerId")
                obs_id = obs_data.get("id")
                value = obs_data.get("value")
                timestamp_str = obs_data.get("timestamp")

                if not all([charger_id, obs_id is not None, value is not None]):
                    continue

                # Parse timestamp
                if timestamp_str:
                    timestamp = datetime.fromisoformat(
                        timestamp_str.replace("Z", "+00:00")
                    )
                else:
                    timestamp = datetime.now(UTC)

                observation = ChargerObservation(
                    charger_id=charger_id,
                    observation_id=obs_id,
                    name=obs_data.get("name", ""),
                    value=value,
                    timestamp=timestamp,
                )

                # Store if we have a mapping
                await self._store_observation(observation)

                # Call custom handler if provided
                if self._on_observation:
                    sensor_id = self._charger_to_sensor.get(charger_id)
                    if sensor_id:
                        await self._on_observation(sensor_id, observation)

            except Exception:
                logger.exception("Error processing observation", data=obs_data)

    async def _store_observation(self, obs: ChargerObservation) -> None:
        """Store an observation to the database."""
        sensor_id = self._charger_to_sensor.get(obs.charger_id)
        if not sensor_id:
            return

        mapping = OBSERVATION_MAPPING.get(obs.observation_id)
        if not mapping:
            return

        attribute, multiplier = mapping

        try:
            # Parse value (can be string or number)
            if isinstance(obs.value, str):
                numeric_value = float(obs.value)
            else:
                numeric_value = float(obs.value)

            # Apply multiplier and store
            stored_value = numeric_value * multiplier

            await save_measurements(
                sensor_id=sensor_id,
                values=[(attribute, obs.timestamp, stored_value)],
            )

            logger.debug(
                "Stored observation",
                sensor_id=sensor_id,
                attribute=attribute.value,
                value=stored_value,
                timestamp=obs.timestamp.isoformat(),
            )

        except (ValueError, TypeError):
            logger.warning(
                "Invalid observation value",
                charger_id=obs.charger_id,
                observation_id=obs.observation_id,
                value=obs.value,
            )


async def run_streaming_worker(account_id: int) -> None:
    """
    Run the Easee streaming worker.

    This is the main entry point for starting the streaming worker.
    It runs indefinitely until cancelled.
    """
    worker = EaseeStreamingWorker(account_id=account_id)
    await worker.run()
