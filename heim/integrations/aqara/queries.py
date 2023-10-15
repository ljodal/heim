from datetime import datetime
from typing import Any

from ... import db
from .models import AqaraAccount

######################
# Account management #
######################


async def create_aqara_account(
    *,
    account_id: int,
    username: str,
    access_token: str,
    refresh_token: str,
    expires_at: datetime,
) -> int:
    return await db.fetchval(  # type: ignore[no-any-return]
        """
        INSERT INTO aqara_account (
            account_id, username, access_token, refresh_token, expires_at
        )
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id
        """,
        account_id,
        username,
        access_token,
        refresh_token,
        expires_at,
    )


async def get_aqara_account(
    *, account_id: int, for_update: bool = False
) -> AqaraAccount:
    row = await db.fetchrow(
        f"""
        SELECT
            id, account_id, username, access_token, refresh_token, expires_at
        FROM aqara_account
        WHERE account_id = $1
        {"FOR UPDATE" if for_update else ""}
        """,
        account_id,
    )
    if not row:
        raise ValueError(f"No such Aqara account: {account_id}")
    return AqaraAccount.model_validate(dict(row))


async def update_aqara_account(
    account: AqaraAccount, /, **updates: Any
) -> AqaraAccount:
    # Generate a list of changed fields. This ensures that we do use the
    # potentially untrused input in updates.
    changed_fields = {}
    for field in AqaraAccount.model_fields.keys():
        if field in updates and getattr(account, field) != updates[field]:
            changed_fields[field] = updates[field]

    if not changed_fields:
        return account

    update_sql = ", ".join(f"{field}=${i}" for i, field in enumerate(changed_fields, 1))

    await db.execute(
        f"UPDATE aqara_account SET {update_sql}",
        *changed_fields.values(),
    )

    return account.copy(update=changed_fields)


#####################
# Device management #
#####################


@db.transaction()
async def create_aqara_sensor(
    *, account_id: int, name: str, location_id: int, model: str, aqara_id: str
) -> int:
    aqara_account_id: int = await db.fetchval(
        "SELECT id FROM aqara_account WHERE account_id = $1",
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
        INSERT INTO aqara_sensor (
            aqara_account_id, sensor_id, name, sensor_type, aqara_id
        )
        VALUES ($1, $2, $3, $4, $5)
        """,
        aqara_account_id,
        sensor_id,
        name,
        model,
        aqara_id,
    )

    return sensor_id


async def get_aqara_sensor(
    *, account_id: int, sensor_id: int
) -> tuple[str, str, datetime | None]:
    """
    Get aqara details for a sensor. Returns the aqara_id, model type and the
    latest measurement we have from the sensor.
    """

    row = await db.fetchrow(
        """
        SELECT
            aqara_id,
            sensor_type,
            (
                SELECT MAX(measured_at)
                FROM sensor_measurement
                WHERE sensor_id=sensor_id
            )
        FROM aqara_sensor s
        JOIN aqara_account a ON s.aqara_account_id = a.id
        WHERE a.account_id = $1 AND sensor_id = $2
        """,
        account_id,
        sensor_id,
    )
    if not row:
        raise ValueError(
            f"No Aqara sensor with id={sensor_id} under account {account_id}"
        )
    aqara_id, model, last_update_time = row

    return aqara_id, model, last_update_time
