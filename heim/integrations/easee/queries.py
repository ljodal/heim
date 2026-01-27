from datetime import datetime
from typing import Any

from ... import db
from .models import EaseeAccount

######################
# Account management #
######################


async def create_easee_account(
    *,
    account_id: int,
    username: str,
    access_token: str,
    refresh_token: str,
    expires_at: datetime,
) -> int:
    return await db.fetchval(  # type: ignore[no-any-return]
        """
        INSERT INTO easee_account (
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


async def has_easee_account(*, account_id: int) -> bool:
    """Check if an Easee account is linked for the given account."""
    row = await db.fetchrow(
        "SELECT id FROM easee_account WHERE account_id = $1",
        account_id,
    )
    return row is not None


async def get_easee_account_info(*, account_id: int) -> tuple[int, datetime] | None:
    """Get Easee account info (id, expires_at) or None if not linked."""
    row = await db.fetchrow(
        "SELECT id, expires_at FROM easee_account WHERE account_id = $1",
        account_id,
    )
    if row:
        return row["id"], row["expires_at"]
    return None


async def get_easee_account(
    *, account_id: int, for_update: bool = False
) -> EaseeAccount:
    row = await db.fetchrow(
        f"""
        SELECT
            id, account_id, username, access_token, refresh_token, expires_at
        FROM easee_account
        WHERE account_id = $1
        {"FOR UPDATE" if for_update else ""}
        """,
        account_id,
    )
    if not row:
        raise ValueError(f"No such Easee account: {account_id}")
    return EaseeAccount.model_validate(dict(row))


async def update_easee_account(
    account: EaseeAccount, /, **updates: Any
) -> EaseeAccount:
    # Generate a list of changed fields
    changed_fields = {}
    for field in EaseeAccount.model_fields.keys():
        if field in updates and getattr(account, field) != updates[field]:
            changed_fields[field] = updates[field]

    if not changed_fields:
        return account

    update_sql = ", ".join(f"{field}=${i}" for i, field in enumerate(changed_fields, 2))

    await db.execute(
        f"UPDATE easee_account SET {update_sql} WHERE id = $1",
        account.id,
        *changed_fields.values(),
    )

    return account.model_copy(update=changed_fields)


#####################
# Charger management #
#####################


@db.transaction()
async def create_easee_charger(
    *,
    account_id: int,
    name: str,
    location_id: int,
    charger_id: str,
) -> int:
    easee_account_id: int = await db.fetchval(
        "SELECT id FROM easee_account WHERE account_id = $1",
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
        INSERT INTO easee_charger (
            easee_account_id, sensor_id, name, charger_id
        )
        VALUES ($1, $2, $3, $4)
        """,
        easee_account_id,
        sensor_id,
        name,
        charger_id,
    )

    return sensor_id


async def get_easee_chargers(*, account_id: int) -> list[tuple[int, str, str]]:
    """
    Get all Easee chargers for an account.

    Returns list of (sensor_id, name, charger_id).
    """
    rows = await db.fetch(
        """
        SELECT c.sensor_id, c.name, c.charger_id
        FROM easee_charger c
        JOIN easee_account a ON c.easee_account_id = a.id
        WHERE a.account_id = $1
        ORDER BY c.sensor_id
        """,
        account_id,
    )
    return [(row["sensor_id"], row["name"], row["charger_id"]) for row in rows]


async def get_easee_charger(
    *, account_id: int, sensor_id: int
) -> tuple[str, datetime | None]:
    """
    Get Easee charger details. Returns the charger_id and the latest
    measurement timestamp.
    """
    row = await db.fetchrow(
        """
        SELECT
            charger_id,
            (
                SELECT MAX(measured_at)
                FROM sensor_measurement sm
                WHERE sm.sensor_id = c.sensor_id
            ) as last_measurement
        FROM easee_charger c
        JOIN easee_account a ON c.easee_account_id = a.id
        WHERE a.account_id = $1 AND c.sensor_id = $2
        """,
        account_id,
        sensor_id,
    )
    if not row:
        raise ValueError(
            f"No Easee charger with sensor_id={sensor_id} under account {account_id}"
        )
    return row["charger_id"], row["last_measurement"]


async def get_easee_charger_id(*, sensor_id: int) -> str | None:
    """Get the Easee charger ID for a sensor."""
    row = await db.fetchrow(
        "SELECT charger_id FROM easee_charger WHERE sensor_id = $1",
        sensor_id,
    )
    return row["charger_id"] if row else None
