from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from email.utils import parsedate_to_datetime

import structlog

from ...forecasts.queries import create_forecast_instance, get_forecast_coordinate
from ...sensors.types import Attribute
from ...tasks import task
from .client import get_location_forecast
from .types import ForecastResponse

ATTRIBUTE_MAP: tuple[tuple[Attribute, str, Callable[[Decimal], int]], ...] = (
    (Attribute.AIR_TEMPERATURE, "air_temperature", lambda value: round(value * 100)),
    (Attribute.HUMIDITY, "relative_humidity", lambda value: round(value * 100)),
    (Attribute.CLOUD_COVER, "cloud_area_fraction", lambda value: round(value * 100)),
)

logger = structlog.get_logger()


@task(name="load-yr-forecast", allow_skip=True)
async def load_yr_forecast(
    *, forecast_id: int, if_modified_since: str | None = None
) -> None:
    """
    Update the given YR forecast.

    This task will schedule its next run based on the response headers.
    """

    coordinate = await get_forecast_coordinate(forecast_id=forecast_id)
    if not coordinate:
        raise RuntimeError(f"Missing coordinate for forecast: {forecast_id}")

    response = await get_location_forecast(
        coordinate=coordinate, if_modified_since=if_modified_since
    )

    # Figure out when to update again. If the Expires header was provided we
    # use that, if not we try again in 1 minute. Also ensure we never try more
    # than once a minute, regardless of the Expires header
    next_update = datetime.now(timezone.utc) + timedelta(minutes=1)
    if "Expires" in response.headers:
        next_update = max(
            next_update,
            parsedate_to_datetime(response.headers["Expires"]) + timedelta(minutes=1),
        )

    if response.status_code == 200:
        forecast = ForecastResponse.model_validate_json(response.text)
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
    elif response.status_code == 304:
        logger.info("Got 304 Not Modified status code from YR")
    else:
        raise RuntimeError(
            f"Got unexpected status code {response.status_code} "
            f"when updating YR forecast"
        )

    if_modified_since = response.headers.get("Last-Modified", None)

    # Schedule the task to run again when yr says it's okay.
    await load_yr_forecast(
        forecast_id=forecast_id, if_modified_since=if_modified_since
    ).defer(run_at=next_update)
