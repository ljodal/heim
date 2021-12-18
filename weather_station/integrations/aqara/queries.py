from datetime import datetime

from ... import db
from .models import AqaraAccount


@db.transaction()
async def create_aqara_sensor(
    *, id: int, aqara_account_id: int, name: str, location_id: int
) -> int:

    account_id: int = await db.fetchval(
        "SELECT account_id FROM aqara_account WHERE id = $1",
        aqara_account_id,
    )

    sensor_id: int = await db.fetchval(
        """
        INSERT INTO sensor (account_id, location_id, name)
        VALUES ($1, $2, $3) RETURNING id
        """,
        account_id,
        location_id,
        name,
    )

    return await db.fetchval(
        """
        INSERT INTO aqara_sensor (aqara_account_id, sensor_id, name)
        VALUES ($1, $2, $3) RETURNING id
        """,
        account_id,
        sensor_id,
        name,
    )


async def create_aqara_account(
    *,
    account_id: int,
    username: str,
    access_token: str,
    refresh_token: str,
    expires_at: datetime,
) -> int:
    return await db.fetchval(
        """
        INSERT INTO aqara_account (
            account_id, username, access_token, refresh_token, expires_at
        ) VALUES ($1, $2, $3, $4, $5) RETURNING id
        """,
        account_id,
        username,
        access_token,
        refresh_token,
        expires_at,
    )


async def get_aqara_account(*, account_id: int) -> AqaraAccount:

    row = await db.fetchrow(
        """
        SELECT
            id, account_id, username, access_token, refresh_token, exprire_at
        FROM aqara_account
        WHERE account_id = $1
        """,
        account_id,
    )
    return AqaraAccount.parse_obj(row)


async def update_aqara_account(*, account: AqaraAccount, **updates) -> AqaraAccount:

    # Generate a list of changed fields. This ensures that we do use the
    # potentially untrused input in updates.
    changed_fields = {}
    for field in AqaraAccount.__fields__:
        if field in updates and getattr(account, field) != updates[field]:
            changed_fields[field] = updates[field]

    if not changed_fields:
        return account

    update_sql = ", ".join(f"{field}=${i}" for i, field in enumerate(changed_fields))

    await db.execute(
        f"UPDATE aqara_acount SET {update_sql}",
        *changed_fields.values(),
    )

    return account.copy(update=changed_fields)