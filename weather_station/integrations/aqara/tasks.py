from ...tasks import task


@task(name="fetch-aqara-sensor-data")
async def fetch_aqara_sensor_data(aqara_account_id: int) -> None:
    pass
