from datetime import datetime
from typing import Any

from ... import db
from .models import NetatmoAccount

######################
# Account management #
######################


async def create_netatmo_account(
    *,
    account_id: int,
    access_token: str,
    refresh_token: str,
    expires_at: datetime,
) -> int:
    return await db.fetchval(  # type: ignore[no-any-return]
        """
        INSERT INTO netatmo_account (
            account_id, access_token, refresh_token, expires_at
        )
        VALUES ($1, $2, $3, $4)
        RETURNING id
        """,
        account_id,
        access_token,
        refresh_token,
        expires_at,
    )


async def has_netatmo_account(*, account_id: int) -> bool:
    """Check if a Netatmo account is linked for the given account."""
    row = await db.fetchrow(
        "SELECT id FROM netatmo_account WHERE account_id = $1",
        account_id,
    )
    return row is not None


async def get_netatmo_account_info(*, account_id: int) -> tuple[int, datetime] | None:
    """Get Netatmo account info (id, expires_at) or None if not linked."""
    row = await db.fetchrow(
        "SELECT id, expires_at FROM netatmo_account WHERE account_id = $1",
        account_id,
    )
    if row:
        return row["id"], row["expires_at"]
    return None


async def get_netatmo_account(
    *, account_id: int, for_update: bool = False
) -> NetatmoAccount:
    row = await db.fetchrow(
        f"""
        SELECT
            id, account_id, access_token, refresh_token, expires_at
        FROM netatmo_account
        WHERE account_id = $1
        {"FOR UPDATE" if for_update else ""}
        """,
        account_id,
    )
    if not row:
        raise ValueError(f"No such Netatmo account: {account_id}")
    return NetatmoAccount.model_validate(dict(row))


async def update_netatmo_account(
    account: NetatmoAccount, /, **updates: Any
) -> NetatmoAccount:
    # Generate a list of changed fields. This ensures that we do use the
    # potentially untrusted input in updates.
    changed_fields = {}
    for field in NetatmoAccount.model_fields.keys():
        if field in updates and getattr(account, field) != updates[field]:
            changed_fields[field] = updates[field]

    if not changed_fields:
        return account

    update_sql = ", ".join(f"{field}=${i}" for i, field in enumerate(changed_fields, 2))

    await db.execute(
        f"UPDATE netatmo_account SET {update_sql} WHERE id = $1",
        account.id,
        *changed_fields.values(),
    )

    return account.model_copy(update=changed_fields)


#####################
# Sensor management #
#####################


@db.transaction()
async def create_netatmo_sensor(
    *,
    account_id: int,
    name: str,
    location_id: int,
    module_type: str,
    netatmo_id: str,
    station_id: str,
) -> int:
    netatmo_account_id: int = await db.fetchval(
        "SELECT id FROM netatmo_account WHERE account_id = $1",
        account_id,
    )

    sensor_id: int = await db.fetchval(
        """
        INSERT INTO sensor (account_id, location_id, name)
        VALUES ($1, $2, $3)
        RETURNING id
        """,
        account_id,
        location_id,
        name,
    )

    await db.execute(
        """
        INSERT INTO netatmo_sensor (
            netatmo_account_id, sensor_id, name, module_type, netatmo_id, station_id
        )
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        netatmo_account_id,
        sensor_id,
        name,
        module_type,
        netatmo_id,
        station_id,
    )

    return sensor_id


async def get_netatmo_sensors(*, account_id: int) -> list[tuple[int, str, str]]:
    """
    Get all netatmo sensors for an account.

    Returns list of (sensor_id, name, module_type).
    """
    rows = await db.fetch(
        """
        SELECT s.sensor_id, s.name, s.module_type
        FROM netatmo_sensor s
        JOIN netatmo_account a ON s.netatmo_account_id = a.id
        WHERE a.account_id = $1
        ORDER BY s.sensor_id
        """,
        account_id,
    )
    return [(row["sensor_id"], row["name"], row["module_type"]) for row in rows]


async def get_netatmo_sensor(
    *, account_id: int, sensor_id: int
) -> tuple[str, str, str, datetime | None]:
    """
    Get netatmo details for a sensor. Returns the netatmo_id, station_id, module_type
    and the latest measurement we have from the sensor.
    """

    row = await db.fetchrow(
        """
        SELECT
            netatmo_id,
            station_id,
            module_type,
            (
                SELECT MAX(measured_at)
                FROM sensor_measurement sm
                WHERE sm.sensor_id = s.sensor_id
            )
        FROM netatmo_sensor s
        JOIN netatmo_account a ON s.netatmo_account_id = a.id
        WHERE a.account_id = $1 AND s.sensor_id = $2
        """,
        account_id,
        sensor_id,
    )
    if not row:
        raise ValueError(
            f"No Netatmo sensor with id={sensor_id} under account {account_id}"
        )
    netatmo_id, station_id, module_type, last_update_time = row

    return netatmo_id, station_id, module_type, last_update_time


async def get_netatmo_sensor_device_id(*, sensor_id: int) -> str | None:
    """Get the Netatmo device ID for a sensor."""
    row = await db.fetchrow(
        "SELECT netatmo_id FROM netatmo_sensor WHERE sensor_id = $1",
        sensor_id,
    )
    return row["netatmo_id"] if row else None
