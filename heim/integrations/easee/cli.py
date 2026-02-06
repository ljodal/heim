from datetime import UTC, datetime, timedelta

import click

from ... import db
from .client import EaseeClient
from .queries import (
    create_easee_account,
    create_easee_charger,
    get_easee_chargers,
)
from .tasks import update_charger_state, update_hourly_usage


@click.group(name="easee", help="Manage Easee chargers and accounts")
def cli() -> None:
    pass


#############
# Accounts #
#############


@cli.group(help="Manage linked Easee accounts")
def accounts() -> None:
    pass


@accounts.command(name="create", help="Link an Easee account by logging in")
@click.option("--account-id", "-a", required=True, type=int, help="Heim account ID")
@click.option("--username", required=True, help="Easee username (email)")
@click.option(
    "--password", required=True, prompt=True, hide_input=True, help="Easee password"
)
async def create_account(account_id: int, username: str, password: str) -> None:
    """Create a new Easee account by logging in with credentials."""
    async with EaseeClient() as client:
        click.echo(f"Logging in as {username}...")
        result = await client.login(username=username, password=password)

        await create_easee_account(
            account_id=account_id,
            username=username,
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            expires_at=datetime.now(UTC) + timedelta(seconds=result.expires_in),
        )

        click.echo(f"Easee account created for {username}")


############
# Chargers #
############


@cli.group(help="Manage Easee chargers")
def chargers() -> None:
    pass


@chargers.command(name="list")
@click.option("--account-id", "-a", required=True, type=int, help="Account ID")
@db.setup()
@EaseeClient.authenticated()
async def list_chargers_remote(client: EaseeClient, *, account_id: int) -> None:
    """List all chargers available from the Easee API."""
    chargers_list = await client.get_chargers()
    if not chargers_list:
        click.echo("No chargers found")
        return

    click.echo(f"Found {len(chargers_list)} charger(s):")
    for charger in chargers_list:
        click.echo(f"  - {charger.id}: {charger.name}")


@chargers.command(name="state")
@click.option("--account-id", "-a", required=True, type=int, help="Account ID")
@click.option("--charger-id", required=True, help="Easee charger ID")
@db.setup()
@EaseeClient.authenticated()
async def get_charger_state_cmd(
    client: EaseeClient, *, account_id: int, charger_id: str
) -> None:
    """Get the current state of a charger."""
    state = await client.get_charger_state(charger_id)

    click.echo(f"Charger: {charger_id}")
    click.echo(f"  Online: {state.is_online}")
    click.echo(f"  Op Mode: {state.charger_op_mode}")
    click.echo(f"  Power: {state.total_power} kW")
    click.echo(f"  Session Energy: {state.session_energy} kWh")
    click.echo(f"  Lifetime Energy: {state.lifetime_energy} kWh")
    click.echo(f"  Output Current: {state.output_current} A")
    click.echo(f"  Cable Locked: {state.cable_locked}")


@chargers.command(name="create")
@click.option("--account-id", "-a", required=True, type=int, help="Account ID")
@click.option("--location-id", "-l", required=True, type=int, help="Location ID")
@click.option("--name", required=True, help="Display name for the charger")
@click.option("--charger-id", required=True, help="Easee charger ID (serial number)")
@db.setup()
async def create_charger_cmd(
    account_id: int, location_id: int, name: str, charger_id: str
) -> None:
    """Register an Easee charger as a sensor."""
    async with db.transaction():
        sensor_id = await create_easee_charger(
            account_id=account_id,
            location_id=location_id,
            name=name,
            charger_id=charger_id,
        )

        # Schedule periodic updates
        await update_charger_state(account_id=account_id, sensor_id=sensor_id).schedule(
            cron_expression="*/5 * * * *"
        )

    click.echo(f"Created charger '{name}' with sensor ID {sensor_id}")


@chargers.command(name="registered")
@click.option("--account-id", "-a", required=True, type=int, help="Account ID")
@db.setup()
async def list_registered_chargers(account_id: int) -> None:
    """List all registered chargers for an account."""
    chargers_list = await get_easee_chargers(account_id=account_id)
    if not chargers_list:
        click.echo("No chargers registered")
        return

    click.echo(f"Registered chargers ({len(chargers_list)}):")
    for sensor_id, name, charger_id in chargers_list:
        click.echo(f"  - Sensor {sensor_id}: {name} ({charger_id})")


@chargers.command(name="update")
@click.option("--account-id", "-a", required=True, type=int, help="Account ID")
@click.option("--sensor-id", required=True, type=int, help="Sensor ID")
@db.setup()
async def update_charger_cmd(account_id: int, sensor_id: int) -> None:
    """Fetch and save the current state of a charger."""
    await update_charger_state(account_id=account_id, sensor_id=sensor_id)
    click.echo("Charger state updated")


@chargers.command(name="backfill")
@click.option("--account-id", "-a", required=True, type=int, help="Account ID")
@click.option("--sensor-id", required=True, type=int, help="Sensor ID")
@click.option("--days", default=7, type=int, help="Number of days to backfill")
@db.setup()
async def backfill_charger(account_id: int, sensor_id: int, days: int) -> None:
    """Backfill hourly energy usage for a charger."""
    from_time = datetime.now(UTC) - timedelta(days=days)
    await update_hourly_usage(
        account_id=account_id,
        sensor_id=sensor_id,
        from_time=from_time,
    )
    click.echo(f"Backfilled {days} days of hourly usage")


#############
# Streaming #
#############


@cli.command(name="stream")
@click.option("--account-id", "-a", required=True, type=int, help="Account ID")
@db.setup_pool()
async def stream_chargers(account_id: int) -> None:
    """
    Start real-time streaming of charger data via SignalR.

    This maintains a persistent WebSocket connection and receives
    live updates from all registered chargers. Run this as a
    long-running worker process.
    """
    from .streaming import run_streaming_worker

    click.echo(f"Starting Easee streaming worker for account {account_id}...")
    click.echo("Press Ctrl+C to stop")
    await run_streaming_worker(account_id=account_id)
