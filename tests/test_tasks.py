from datetime import UTC, datetime, timedelta

import pytest
from heim import db
from heim.tasks import task
from heim.tasks.queries import delete_old_tasks, get_next_task

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def clear_tasks(connection: None) -> None:
    await db.execute("TRUNCATE task CASCADE")


@task(name="my-test-task")
async def my_test_task(*, arg: int) -> None:
    pass


async def test_schedule_without_time_task(connection: None, clear_tasks: None) -> None:
    await my_test_task(arg=1).defer()

    task = await get_next_task()
    assert task

    task_id, name, arguments, run_at, from_schedule_id = task
    assert task_id > 0
    assert name == "my-test-task"
    assert arguments == {"arg": 1}
    assert run_at < datetime.now(UTC)
    assert from_schedule_id is None


async def test_schedule_with_time_task(connection: None, clear_tasks: None) -> None:
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


async def test_delete_old_tasks(connection: None, clear_tasks: None) -> None:
    # Insert tasks with different finished_at times
    old_time = datetime.now(UTC) - timedelta(days=10)  # 10 days ago
    recent_time = datetime.now(UTC) - timedelta(days=3)  # 3 days ago

    # Create an old finished task (should be deleted)
    await db.execute(
        """
        INSERT INTO task (name, arguments, run_at, started_at, finished_at)
        VALUES ('old-task', '{}', $1, $1, $1)
        """,
        old_time,
    )

    # Create a recent finished task (should NOT be deleted)
    await db.execute(
        """
        INSERT INTO task (name, arguments, run_at, started_at, finished_at)
        VALUES ('recent-task', '{}', $1, $1, $1)
        """,
        recent_time,
    )

    # Create a pending task (should NOT be deleted - no finished_at)
    await db.execute(
        """
        INSERT INTO task (name, arguments, run_at)
        VALUES ('pending-task', '{}', $1)
        """,
        datetime.now(UTC),
    )

    # Run the cleanup
    await delete_old_tasks()

    # Check what's left
    remaining = await db.fetch("SELECT name FROM task ORDER BY name")
    names = [row["name"] for row in remaining]

    assert "old-task" not in names  # Should be deleted
    assert "recent-task" in names  # Should remain
    assert "pending-task" in names  # Should remain
