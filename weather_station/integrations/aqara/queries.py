from ... import db


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
