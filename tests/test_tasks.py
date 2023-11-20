from datetime import datetime, timedelta, timezone

import pytest

from heim import db
from heim.tasks import task
from heim.tasks.queries import get_next_task

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def clear_tasks(connection: None) -> None:
    await db.execute("TRUNCATE task CASCADE")


@task(name="my-test-task")
async def my_test_task(*, arg: int) -> None:
    pass


async def test_schedule_without_time_task(connection: None, clear_tasks: None) -> None:
    await my_test_task.defer(arguments={"arg": 1})

    task = await get_next_task()
    assert task

    task_id, name, arguments, run_at, from_schedule_id = task
    assert task_id > 0
    assert name == "my-test-task"
    assert arguments == {"arg": 1}
    assert run_at < datetime.now(timezone.utc)
    assert from_schedule_id is None


async def test_schedule_with_time_task(connection: None, clear_tasks: None) -> None:
    run_at = datetime.now(timezone.utc) + timedelta(days=1)
    await my_test_task.defer(arguments={"arg": 1}, run_at=run_at)

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
