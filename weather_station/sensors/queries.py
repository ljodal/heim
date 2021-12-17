from datetime import datetime

from .. import db
from .types import Attribute


async def register_sensor_data(
    *, sensor_id: int, attributes: dict[Attribute, list[tuple[datetime, float]]]
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
            for attribute, values in attributes.items()
            for timestamp, value in values
        ],
    )
