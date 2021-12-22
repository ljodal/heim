from datetime import datetime, timedelta, timezone
from decimal import Decimal
from email.utils import parsedate_to_datetime
from typing import Callable

from ...forecasts.queries import create_forecast_instance
from ...sensors.types import Attribute
from ...tasks import task
from .client import get_location_forecast
from .queries import get_forecast_coordinate
from .types import ForecastResponse

ATTRIBUTE_MAP: tuple[tuple[Attribute, str, Callable[[Decimal], int]], ...] = (
    (Attribute.AIR_TEMPERATURE, "air_temperature", lambda value: round(value * 100)),
    (Attribute.HUMIDITY, "relative_humidity", lambda value: round(value * 100)),
    (Attribute.CLOUD_COVER, "cloud_area_fraction", lambda value: round(value * 100)),
)


@task(name="load-yr-forecast", allow_skip=True)
async def load_yr_forecast(
    *, forecast_id: int, if_modified_since: str | None = None
) -> None:
    """
    Update the given YR forecast.

    This task will schedule its next run based on the response headers.
    """

    coordinate = await get_forecast_coordinate(forecast_id=forecast_id)

    response = await get_location_forecast(
        coordinate=coordinate, if_modified_since=if_modified_since
    )

    # Figure out when to update again. If the Expires header was provided we
    # use that, if not we try again in 10 minutes.
    if "Expires" in response.headers:
        next_update = parsedate_to_datetime(response.headers["Expires"])
    else:
        next_update = datetime.now(timezone.utc) + timedelta(minutes=10)

    if response.status_code == 200:
        forecast = ForecastResponse.parse_obj(response.json())
        values = [
            (
                attribute,
                step.time,
                converter(getattr(step.data.instant.details, name)),
            )
            for step in forecast.properties.timeseries
            for attribute, name, converter in ATTRIBUTE_MAP
            if getattr(step.data.instant.details, name, None) is not None
        ]

        await create_forecast_instance(
            forecast_id=forecast_id,
            forecast_time=forecast.properties.meta.updated_at,
            values=values,
        )
    elif response.status_code != 304:
        raise RuntimeError(
            f"Got unexpected statuc code {response.status_code} "
            f"when updating YR forecast"
        )

    if_modified_since = response.headers.get("Last-Modified", None)

    # Schedule the task to run again when yr says it's okay.
    await load_yr_forecast.defer(  # type: ignore
        arguments={"forecast_id": forecast_id, "if_modified_since": if_modified_since},
        run_at=next_update,
    )
