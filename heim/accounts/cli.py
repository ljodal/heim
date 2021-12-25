import click

from .. import db
from .queries import create_account, create_location


@click.group(name="account")
def cli() -> None:
    pass


@cli.command(help="Create a new account")
@click.option("--username", required=True)
@click.password_option("--password", required=True)
@db.setup()
async def create(*, username: str, password: str) -> None:
    account_id = await create_account(username=username, password=password)
    click.echo(f"Created account with ID {account_id}")


@cli.command(name="create-location", help="Create a new location")
@click.option("--name", required=True)
@click.option("--account-id", type=int, required=True)
@click.option("--longitude", type=float, required=True)
@click.option("--latitude", type=float, required=True)
@db.setup()
async def add_location(
    *, name: str, account_id: int, longitude: float, latitude: float
) -> None:
    location_id = await create_location(
        account_id=account_id, name=name, coordinate=(longitude, latitude)
    )
    click.echo(f"Created location with ID {location_id}")
