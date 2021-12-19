from datetime import datetime
from typing import Iterable

from .. import db
from .types import Attribute


async def save_measurements(
    *, sensor_id: int, values: Iterable[tuple[Attribute, datetime, float]]
) -> None:
    """
    Insert a forecast instance.
    """

    await db.executemany(
        """
        INSERT INTO sensor_measurement (sensor_id, attribute, measured_at, value)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (sensor_id, attribute, measured_at) DO NOTHING
        """,
        [
            (sensor_id, attribute, timestamp, value)
            for attribute, timestamp, value in values
        ],
    )
