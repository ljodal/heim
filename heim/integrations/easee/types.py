from datetime import datetime

from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    """Response from login/refresh token endpoint."""

    access_token: str = Field(alias="accessToken")
    refresh_token: str = Field(alias="refreshToken")
    expires_in: int = Field(alias="expiresIn")


class Charger(BaseModel):
    """A single charger from the API."""

    id: str
    name: str
    color: int | None = None
    created_on: datetime | None = Field(default=None, alias="createdOn")
    updated_on: datetime | None = Field(default=None, alias="updatedOn")
    product_code: int | None = Field(default=None, alias="productCode")


class ChargerState(BaseModel):
    """Current state of a charger."""

    charger_op_mode: int | None = Field(default=None, alias="chargerOpMode")
    total_power: float | None = Field(default=None, alias="totalPower")
    session_energy: float | None = Field(default=None, alias="sessionEnergy")
    lifetime_energy: float | None = Field(default=None, alias="lifetimeEnergy")
    energy_per_hour: float | None = Field(default=None, alias="energyPerHour")

    # Phase currents (amps)
    in_current_t2: float | None = Field(default=None, alias="inCurrentT2")
    in_current_t3: float | None = Field(default=None, alias="inCurrentT3")
    in_current_t4: float | None = Field(default=None, alias="inCurrentT4")
    in_current_t5: float | None = Field(default=None, alias="inCurrentT5")
    output_current: float | None = Field(default=None, alias="outputCurrent")

    # Phase voltages (volts)
    in_voltage_t1_t2: float | None = Field(default=None, alias="inVoltageT1T2")
    in_voltage_t2_t3: float | None = Field(default=None, alias="inVoltageT2T3")
    in_voltage_t3_t4: float | None = Field(default=None, alias="inVoltageT3T4")
    in_voltage_t4_t5: float | None = Field(default=None, alias="inVoltageT4T5")

    # Dynamic limits
    dynamic_charger_current: float | None = Field(
        default=None, alias="dynamicChargerCurrent"
    )
    dynamic_circuit_current_p1: float | None = Field(
        default=None, alias="dynamicCircuitCurrentP1"
    )
    dynamic_circuit_current_p2: float | None = Field(
        default=None, alias="dynamicCircuitCurrentP2"
    )
    dynamic_circuit_current_p3: float | None = Field(
        default=None, alias="dynamicCircuitCurrentP3"
    )

    # Cable info
    cable_locked: bool | None = Field(default=None, alias="cableLocked")
    cable_rating: float | None = Field(default=None, alias="cableRating")

    # Charging state info
    reason_for_no_current: int | None = Field(default=None, alias="reasonForNoCurrent")
    is_online: bool | None = Field(default=None, alias="isOnline")


class HourlyUsage(BaseModel):
    """Hourly energy usage data point."""

    date: datetime
    energy_used: float = Field(alias="energyUsed")


class ChargingSession(BaseModel):
    """A charging session."""

    session_id: str | None = Field(default=None, alias="sessionId")
    charger_id: str = Field(alias="chargerId")
    session_start: datetime | None = Field(default=None, alias="sessionStart")
    session_end: datetime | None = Field(default=None, alias="sessionEnd")
    session_energy: float | None = Field(default=None, alias="sessionEnergy")
    charge_duration_seconds: int | None = Field(
        default=None, alias="chargeDurationInSeconds"
    )


class Site(BaseModel):
    """A site containing chargers."""

    id: int
    name: str
    chargers: list[Charger] = Field(default_factory=list)
