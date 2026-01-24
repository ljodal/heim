import os
import webbrowser
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import click

from ... import db
from .client import NetatmoClient
from .queries import create_netatmo_account, create_netatmo_sensor, get_netatmo_sensors
from .services import with_netatmo_client
from .tasks import update_sensor_data

# OAuth URLs
AUTH_BASE_URL = "https://api.netatmo.com/oauth2/authorize"
SCOPES = ["read_station"]


def get_redirect_uri() -> str:
    """Get the redirect URI, defaulting to the heim server callback."""
    return os.getenv("NETATMO_REDIRECT_URI", "http://localhost:8000/api/netatmo/callback")


@click.group(name="netatmo", help="Manage Netatmo weather stations")
def cli() -> None:
    pass


######################
# Account management #
######################


@cli.group(help="Manage linked Netatmo accounts")
def accounts() -> None:
    pass


@accounts.command(name="auth", help="Open browser to authorize with Netatmo")
@click.option("--account-id", "-a", type=int, default=1, help="Heim account ID")
def auth(*, account_id: int) -> None:
    """
    Open a browser to authorize with Netatmo.

    After authorization, you'll be redirected to the heim server which will
    automatically link your Netatmo account.
    """
    client_id = os.getenv("NETATMO_CLIENT_ID")
    if not client_id:
        click.echo("Error: NETATMO_CLIENT_ID environment variable not set")
        raise SystemExit(1)

    redirect_uri = get_redirect_uri()

    # Use state parameter to pass account_id through OAuth flow
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(SCOPES),
        "state": str(account_id),
    }

    auth_url = f"{AUTH_BASE_URL}?{urlencode(params)}"

    click.echo(f"Linking to Heim account #{account_id}")
    click.echo("Opening browser for Netatmo authorization...")
    click.echo(f"\nIf the browser doesn't open, visit:\n{auth_url}\n")
    click.echo("Make sure the heim server is running (uvicorn heim.server:app)")
    webbrowser.open(auth_url)


@accounts.command(name="create", help="Link a Netatmo account to a Heim account")
@click.option("--account-id", type=int, help="Heim account ID", required=True)
@click.option("--auth-code", help="Auth code from OAuth redirect", required=True)
@db.setup()
async def create_account(*, account_id: int, auth_code: str) -> None:
    """
    Link a Netatmo account using an authorization code.

    Run 'heim netatmo accounts auth' first to get the authorization code.
    """
    redirect_uri = get_redirect_uri()

    async with NetatmoClient() as client:
        result = await client.get_token_from_code(
            code=auth_code, redirect_uri=redirect_uri
        )

    await create_netatmo_account(
        account_id=account_id,
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        expires_at=datetime.now(UTC) + timedelta(seconds=result.expires_in),
    )

    click.echo("Netatmo account linked successfully!")


#####################
# Device management #
#####################


@cli.group(help="Manage Netatmo devices")
def devices() -> None:
    pass


@devices.command(name="list")
@click.option("--account-id", "-a", type=int, help="Account id", required=True)
@db.setup()
@with_netatmo_client
async def list_devices(client: NetatmoClient, *, account_id: int) -> None:
    """
    List all Netatmo weather stations and their modules.
    """
    data = await client.get_stations_data()

    for station in data.devices:
        click.echo(f"\nStation: {station.station_name} ({station.home_name})")
        click.echo(f"  ID: {station.id}")
        click.echo(f"  Type: {station.type}")
        click.echo(f"  Data types: {', '.join(station.data_type)}")

        if station.dashboard_data:
            dashboard = station.dashboard_data
            click.echo("  Current readings:")
            if dashboard.temperature is not None:
                click.echo(f"    Temperature: {dashboard.temperature}°C")
            if dashboard.humidity is not None:
                click.echo(f"    Humidity: {dashboard.humidity}%")
            if dashboard.pressure is not None:
                click.echo(f"    Pressure: {dashboard.pressure} mbar")
            if dashboard.co2 is not None:
                click.echo(f"    CO2: {dashboard.co2} ppm")
            if dashboard.noise is not None:
                click.echo(f"    Noise: {dashboard.noise} dB")

        for module in station.modules:
            click.echo(f"\n  Module: {module.module_name}")
            click.echo(f"    ID: {module.id}")
            click.echo(f"    Type: {module.type}")
            click.echo(f"    Data types: {', '.join(module.data_type)}")
            if module.battery_percent is not None:
                click.echo(f"    Battery: {module.battery_percent}%")

            if module.dashboard_data:
                dashboard = module.dashboard_data
                click.echo("    Current readings:")
                if dashboard.temperature is not None:
                    click.echo(f"      Temperature: {dashboard.temperature}°C")
                if dashboard.humidity is not None:
                    click.echo(f"      Humidity: {dashboard.humidity}%")
                if dashboard.co2 is not None:
                    click.echo(f"      CO2: {dashboard.co2} ppm")
                if dashboard.rain is not None:
                    click.echo(f"      Rain: {dashboard.rain} mm")
                if dashboard.wind_strength is not None:
                    click.echo(f"      Wind: {dashboard.wind_strength} km/h")


@devices.command(name="create")
@click.option("--name", help="Sensor name", required=True)
@click.option("--netatmo-id", help="Netatmo module ID", required=True)
@click.option("--location-id", type=int, help="Location ID", required=True)
@click.option("--account-id", "-a", type=int, help="Account id", required=True)
@db.setup()
@with_netatmo_client
async def create_device(
    client: NetatmoClient,
    *,
    account_id: int,
    name: str,
    location_id: int,
    netatmo_id: str,
) -> None:
    """
    Create a sensor from a Netatmo module and schedule data collection.
    """
    # Find the module in the user's stations
    data = await client.get_stations_data()

    module_type: str | None = None
    station_id: str | None = None

    for station in data.devices:
        # Check if it's the main station
        if station.id == netatmo_id:
            module_type = station.type
            station_id = station.id
            break

        # Check modules
        for module in station.modules:
            if module.id == netatmo_id:
                module_type = module.type
                station_id = station.id
                break

        if module_type:
            break

    if not module_type or not station_id:
        click.echo(f"Error: Module with ID '{netatmo_id}' not found")
        raise SystemExit(1)

    async with db.transaction():
        sensor_id = await create_netatmo_sensor(
            account_id=account_id,
            name=name,
            location_id=location_id,
            module_type=module_type,
            netatmo_id=netatmo_id,
            station_id=station_id,
        )

        # Schedule every 10 minutes (Netatmo updates less frequently than Aqara)
        await update_sensor_data(account_id=account_id, sensor_id=sensor_id).schedule(
            cron_expression="*/10 * * * *"
        )

    click.echo(f"Created sensor {sensor_id} ({name}) and scheduled data collection")


@devices.command(name="sensors")
@click.option("--account-id", "-a", type=int, help="Account id", required=True)
@db.setup()
async def list_sensors(*, account_id: int) -> None:
    """
    List all registered Netatmo sensors for an account.
    """
    sensors = await get_netatmo_sensors(account_id=account_id)

    if not sensors:
        click.echo("No Netatmo sensors registered for this account.")
        return

    click.echo(f"{'ID':>4}  {'Name':<32}  Type")
    click.echo(f"{'--':>4}  {'----':<32}  ----")
    for sensor_id, name, module_type in sensors:
        click.echo(f"{sensor_id:>4}  {name:<32}  {module_type}")


@devices.command(name="backfill")
@click.option("--sensor-id", type=int, help="Sensor ID to backfill")
@click.option("--account-id", "-a", type=int, help="Account id", required=True)
@click.option("--days", type=int, default=7, help="Number of days to backfill")
@click.pass_context
@db.setup()
async def backfill_sensor(
    ctx: click.Context, *, account_id: int, sensor_id: int | None, days: int
) -> None:
    """
    Backfill historical data for a sensor.

    If no sensor-id is provided, lists available sensors.
    """
    if sensor_id is None:
        sensors = await get_netatmo_sensors(account_id=account_id)
        if not sensors:
            click.echo("No sensors found for this account.")
            return

        click.echo("Available sensors:\n")
        click.echo(f"  {'ID':>4}  {'Name':<32}  Type")
        click.echo(f"  {'--':>4}  {'----':<32}  ----")
        for sid, name, module_type in sensors:
            click.echo(f"  {sid:>4}  {name:<32}  {module_type}")
        click.echo("\nUse --sensor-id to backfill a specific sensor.")
        ctx.exit(1)

    now = datetime.now(UTC)
    from_time = now - timedelta(days=days)

    click.echo(f"Backfilling sensor {sensor_id}, {days} days back...")
    await update_sensor_data(
        account_id=account_id,
        sensor_id=sensor_id,
        from_time=from_time,
        to_time=now,
    )
    click.echo("Done!")
