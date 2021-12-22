from ... import db
from ...forecasts.queries import create_forecast


@db.transaction()
async def create_yr_forecast(
    *, account_id: int, name: str, coordinate: tuple[float, float], location_id: int
) -> int:
    """
    Create a forecast to be populated from YR.
    """

    forecast_id = await create_forecast(
        name=name, account_id=account_id, location_id=location_id
    )

    await db.execute(
        """
        INSERT INTO yr_forecast (account_id, forecast_id, name, coordinate)
        VALUES ($1, $2, $3, $4)
        """,
        account_id,
        forecast_id,
        name,
        coordinate,
    )

    return forecast_id


async def get_forecast_coordinate(*, forecast_id: int) -> tuple[float, float]:
    """
    Get the coordinate for the given forecast.
    """

    return await db.fetchval(
        "SELECT coordinate FROM yr_forecast WHERE forecast_id = $1", forecast_id
    )
