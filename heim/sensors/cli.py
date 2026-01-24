from datetime import datetime

import click

from .. import db
from .queries import (
    add_exclusion,
    list_exclusions,
    remove_exclusion,
    set_outdoor_sensor,
)


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


@cli.command(name="exclude")
@click.option("--account-id", "-a", type=int, required=True, help="Account ID")
@click.option("--sensor-id", "-s", type=int, required=True, help="Sensor ID")
@click.option("--from", "from_time", required=True, help="Start (ISO format)")
@click.option("--until", "until_time", required=True, help="End (ISO format)")
@db.setup()
async def exclude(
    *, account_id: int, sensor_id: int, from_time: str, until_time: str
) -> None:
    """Exclude measurements in a time range."""
    try:
        from_dt = datetime.fromisoformat(from_time)
        until_dt = datetime.fromisoformat(until_time)
    except ValueError as e:
        raise click.ClickException(f"Invalid date format: {e}") from e

    if from_dt >= until_dt:
        raise click.ClickException("--from must be before --until")

    exclusion_id = await add_exclusion(
        account_id=account_id,
        sensor_id=sensor_id,
        from_time=from_dt,
        until_time=until_dt,
    )
    if exclusion_id:
        click.echo(f"Created exclusion {exclusion_id} for sensor {sensor_id}")
    else:
        click.echo(f"Sensor {sensor_id} not found for account {account_id}", err=True)
        raise SystemExit(1)


@cli.command(name="exclusions")
@click.option("--account-id", "-a", type=int, required=True, help="Account ID")
@click.option("--sensor-id", "-s", type=int, required=True, help="Sensor ID")
@db.setup()
async def exclusions(*, account_id: int, sensor_id: int) -> None:
    """List exclusions for a sensor."""
    rows = await list_exclusions(account_id=account_id, sensor_id=sensor_id)
    if not rows:
        click.echo("No exclusions found.")
        return

    click.echo(f"{'ID':>4}  {'From':<25}  Until")
    click.echo(f"{'--':>4}  {'----':<25}  -----")
    for excl_id, from_time, until_time in rows:
        from_str = from_time.isoformat()
        until_str = until_time.isoformat()
        click.echo(f"{excl_id:>4}  {from_str:<25}  {until_str}")


@cli.command(name="remove-exclusion")
@click.option("--account-id", "-a", type=int, required=True, help="Account ID")
@click.option("--exclusion-id", "-e", type=int, required=True, help="Exclusion ID")
@db.setup()
async def remove_exclusion_cmd(*, account_id: int, exclusion_id: int) -> None:
    """Remove an exclusion."""
    deleted = await remove_exclusion(account_id=account_id, exclusion_id=exclusion_id)
    if deleted:
        click.echo(f"Removed exclusion {exclusion_id}")
    else:
        click.echo(f"Exclusion {exclusion_id} not found", err=True)
        raise SystemExit(1)
