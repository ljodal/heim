import click

from .. import db
from .queries import create_location


@click.group(name="location", help="Manage locations")
def cli() -> None:
    pass


@cli.command(help="Create a new location")
@click.option("--name", required=True)
@click.option("--account-id", type=int, required=True)
@click.option("--longitude", type=float, required=True)
@click.option("--latitude", type=float, required=True)
@db.setup()
async def create(
    *, name: str, account_id: int, longitude: float, latitude: float
) -> None:
    location_id = await create_location(
        account_id=account_id, name=name, coordinate=(longitude, latitude)
    )
    click.echo(f"Created location with ID {location_id}")
