from datetime import datetime, timedelta, timezone

import click

from ... import db
from .client import AqaraClient
from .queries import create_aqara_account, create_aqara_sensor
from .services import with_aqara_client
from .tasks import update_sensor_data


@click.group(name="aqara", help="Manage Aqara accounts and devices")
def cli() -> None:
    pass


######################
# Account management #
######################


@cli.group(help="Manage linked Aqara accounts")
def accounts() -> None:
    pass


@accounts.command(
    name="get-auth-code", help="Get an auth that can be used to link to an account"
)
@click.option(
    "--aqara-account",
    required=True,
    help="E-mail or phone number of your Aqara account",
)
async def get_token(*, aqara_account: str) -> None:
    async with AqaraClient() as client:
        await client.get_auth_code(account=aqara_account)

    click.echo("Check you e-mail or phone for an auth code")


@accounts.command(name="create", help="Link an Aqara account to an Heim account")
@click.option("--account-id", type=int, help="Heim account ID", required=True)
@click.option(
    "--aqara-account",
    help="E-mail or phone number of your Aqara account",
    required=True,
)
@click.option("--auth-code", help="Auth code from Aqara", required=True)
async def create_account(
    *, account_id: int, aqara_account: str, auth_code: str
) -> None:
    async with AqaraClient() as client:
        result = await client.get_token(code=auth_code, account=aqara_account)

    await create_aqara_account(
        account_id=account_id,
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        username=aqara_account,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=result.expires_in),
    )

    click.echo("Account linked!")


#####################
# Device management #
#####################


@cli.group(help="Manage Aqara devices")
def devices() -> None:
    pass


@devices.command()
@click.option("--account-id", "-a", type=int, help="Account id", required=True)
@db.setup()
@with_aqara_client
async def list(client: AqaraClient, *, account_id: int) -> None:
    """
    List all devices registered to the account.
    """

    print(f"{'Name':32s} {'Model':22s} ID")
    for device in await client.get_all_devices():
        print(f"{device.device_name:32s} {device.model:22s} {device.did}")


@devices.command()
@click.argument("model")
@click.option("--account-id", "-a", type=int, help="Account id", required=True)
@db.setup()
@with_aqara_client
async def resources(client: AqaraClient, *, account_id: int, model: str) -> None:
    """
    List all devices registered to the account.
    """

    for resource in await client.get_device_resources(model=model):
        print()
        print(f"Name.......: {resource.name}")
        print(f"ID.........: {resource.resource_id}")
        print(f"Description: {resource.description}")


@devices.command(name="create")
@click.option("--name", help="Sensor name", required=True)
@click.option("--aqara-id", help="Aqara device ID", required=True)
@click.option("--location-id", type=int, help="Location ID", required=True)
@click.option("--account-id", "-a", type=int, help="Account id", required=True)
@db.setup()
@with_aqara_client
async def create_devices(
    client: AqaraClient, *, account_id: int, name: str, location_id: int, aqara_id: str
) -> None:
    devices = await client.get_all_devices()
    device = next((device for device in devices if device.did == aqara_id), None)
    if device is None:
        raise RuntimeError("Unknown device")

    async with db.transaction():
        sensor_id = await create_aqara_sensor(
            account_id=account_id,
            name=name,
            location_id=location_id,
            model=device.model,
            aqara_id=aqara_id,
        )

        await update_sensor_data.schedule(
            arguments={"account_id": account_id, "sensor_id": sensor_id},
            cron_expression="*/5 * * * *",
        )
