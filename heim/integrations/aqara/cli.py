import click

from ... import db
from .client import AqaraClient
from .queries import create_aqara_sensor
from .services import with_aqara_client
from .tasks import update_sensor_data


@click.group(name="aqara")
def cli() -> None:
    pass


@cli.group()
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


@devices.command()
@click.option("--name", help="Sensor name", required=True)
@click.option("--aqara-id", help="Aqara device ID", required=True)
@click.option("--location-id", type=int, help="Location ID", required=True)
@click.option("--account-id", "-a", type=int, help="Account id", required=True)
@db.setup()
@with_aqara_client
async def create(
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

        await update_sensor_data.schedule(  # type: ignore
            arguments={"account_id": account_id, "sensor_id": sensor_id},
            expression="*/5 * * * *",
        )
