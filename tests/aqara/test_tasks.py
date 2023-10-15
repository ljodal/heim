from datetime import datetime, timedelta, timezone

import pytest
from pytest_mock import MockerFixture

from heim import db
from heim.integrations.aqara.client import AqaraClient
from heim.integrations.aqara.queries import get_aqara_sensor
from heim.integrations.aqara.tasks import update_sensor_data
from heim.integrations.aqara.types import (
    QueryResourceHistoryResult,
    ResourceHistoryPoint,
)

pytestmark = pytest.mark.asyncio


async def test_update_sensor_data(
    sensor_id: int,
    account_id: int,
    resource_id: str,
    aqara_sensor_id: str,
    sensor_model: str,
    mocker: MockerFixture,
) -> None:
    now = datetime.now(timezone.utc)
    scan_id = "test"
    return_values = [
        QueryResourceHistoryResult(
            data=[
                ResourceHistoryPoint.construct(
                    timestamp=now, resource_id=resource_id, value=1, subject_id="foo"
                ),
                ResourceHistoryPoint.construct(
                    timestamp=now + timedelta(hours=1),
                    resource_id=resource_id,
                    value=0,
                    subject_id=aqara_sensor_id,
                ),
            ],
            scan_id=scan_id,
        ),
        QueryResourceHistoryResult(data=[], scan_id=scan_id),
    ]

    mocker.patch.object(AqaraClient, "get_resource_history", side_effect=return_values)

    await update_sensor_data(account_id=account_id, sensor_id=sensor_id)

    aqara_id, model, last_update_time = await get_aqara_sensor(
        account_id=account_id, sensor_id=sensor_id
    )
    assert aqara_id == aqara_sensor_id
    assert model == sensor_model
    assert last_update_time == now + timedelta(hours=1)

    assert (
        await db.fetchval(
            "SELECT COUNT(*) FROM sensor_measurement WHERE sensor_id = $1", sensor_id
        )
        == 2
    )
