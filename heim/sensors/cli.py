import click

from .. import db
from .queries import set_outdoor_sensor


@click.group(name="sensor", help="Manage sensors")
def cli() -> None:
    pass


@cli.command(name="list")
@click.option("--account-id", "-a", type=int, required=True, help="Account ID")
@db.setup()
async def list_sensors(*, account_id: int) -> None:
    """List all sensors for an account."""
    rows = await db.fetch(
        """
        SELECT s.id, s.name, s.is_outdoor, l.name as location_name
        FROM sensor s
        JOIN location l ON l.id = s.location_id
        WHERE s.account_id = $1
        ORDER BY l.name, s.name
        """,
        account_id,
    )
    if not rows:
        click.echo("No sensors found.")
        return

    click.echo(f"{'ID':>4}  {'Name':<30}  {'Location':<20}  Outdoor")
    click.echo(f"{'--':>4}  {'----':<30}  {'--------':<20}  -------")
    for row in rows:
        outdoor = "yes" if row["is_outdoor"] else ""
        name = row["name"] or "(unnamed)"
        click.echo(f"{row['id']:>4}  {name:<30}  {row['location_name']:<20}  {outdoor}")


@cli.command(name="set-outdoor")
@click.option("--account-id", "-a", type=int, required=True, help="Account ID")
@click.option("--sensor-id", "-s", type=int, required=True, help="Sensor ID")
@click.option("--clear", is_flag=True, help="Clear the outdoor flag")
@db.setup()
async def set_outdoor(*, account_id: int, sensor_id: int, clear: bool) -> None:
    """Mark a sensor as outdoor (or clear the flag with --clear)."""
    updated = await set_outdoor_sensor(
        account_id=account_id,
        sensor_id=sensor_id,
        is_outdoor=not clear,
    )
    if updated:
        action = "cleared" if clear else "set"
        click.echo(f"Outdoor flag {action} for sensor {sensor_id}")
    else:
        click.echo(f"Sensor {sensor_id} not found for account {account_id}", err=True)
        raise SystemExit(1)
