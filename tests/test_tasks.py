from datetime import UTC, datetime, timedelta

import pytest
from heim.tasks import task
from heim.tasks.queries import get_next_task

pytestmark = pytest.mark.asyncio


@task(name="my-test-task")
async def my_test_task(*, arg: int) -> None:
    pass


async def test_schedule_without_time_task(connection: None) -> None:
    await my_test_task(arg=1).defer()

    task = await get_next_task()
    assert task

    task_id, name, arguments, run_at, from_schedule_id = task
    assert task_id > 0
    assert name == "my-test-task"
    assert arguments == {"arg": 1}
    assert run_at < datetime.now(UTC)
    assert from_schedule_id is None


async def test_schedule_with_time_task(connection: None) -> None:
    run_at = datetime.now(UTC) + timedelta(days=1)
    await my_test_task(arg=1).defer(run_at=run_at)

    task = await get_next_task()
    assert not task

    task = await get_next_task(now=run_at)
    assert task

    task_id, name, arguments, task_run_at, from_schedule_id = task
    assert task_id > 0
    assert name == "my-test-task"
    assert arguments == {"arg": 1}
    assert task_run_at == run_at
    assert from_schedule_id is None
