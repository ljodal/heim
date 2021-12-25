import click

from .migrations import migrate_db


@click.group(name="db", help="Database related commands")
def cli() -> None:
    pass


@cli.command(help="Apply missing migrations to the database")
async def migrate() -> None:
    click.echo("Migrating the datbabase")
    await migrate_db()
    click.echo("Done migrating the database")
