import click

from ... import db
from ...forecasts.queries import create_forecast
from .tasks import load_yr_forecast


@click.group(name="yr", help="Manage YR forecasts")
def cli() -> None:
    pass


@cli.command(help="Create a new YR forecast for a location")
@click.option("--location-id", type=int, help="Location ID")
@click.option("--account-id", type=int, help="Account ID")
@db.setup()
@db.transaction()
async def create(*, location_id: int, account_id: int) -> None:
    forecast_id = await create_forecast(
        name="YR", account_id=account_id, location_id=location_id
    )

    await load_yr_forecast.defer(arguments={"forecast_id": forecast_id})  # type: ignore
