import click

from .. import db
from .queries import create_account


@click.group(name="account", help="Manage accounts")
def cli() -> None:
    pass


@cli.command(help="Create a new account")
@click.option("--username", required=True)
@click.password_option("--password", required=True)
@db.setup()
async def create(*, username: str, password: str) -> None:
    account_id = await create_account(username=username, password=password)
    click.echo(f"Created account with ID {account_id}")
