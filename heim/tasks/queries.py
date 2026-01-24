from datetime import UTC, datetime
from typing import Any

from croniter import croniter

from .. import db


async def queue_task(
    *, name: str, arguments: dict[str, Any], run_at: datetime | None
) -> int:
    """
    Schedule a task to run at the given time.
    """

    return await db.fetchval(  # type: ignore[no-any-return]
        """
        INSERT INTO task (name, arguments, run_at)
        VALUES ($1, $2, $3) RETURNING id;
        """,
        name,
        arguments,
        run_at or datetime.now(UTC),
    )


async def get_tasks(
    show_all: bool = False,
) -> list[tuple[int, str, dict[str, Any], datetime, int | None]]:
    return await db.fetch(f"""
        SELECT id, name, arguments, run_at, from_schedule_id
        FROM task
        {"WHERE started_at IS NULL" if not show_all else ""}
        ORDER BY run_at
        """)  # type: ignore[return-value]


async def get_next_task(
    *, now: datetime | None = None
) -> tuple[int, str, dict[str, Any], datetime, int | None] | None:
    """
    Get and lock the next pending task. Must be called from within a
    transaction.
    """

    return await db.fetchrow(  # type: ignore[return-value]
        """
        SELECT id, name, arguments, run_at, from_schedule_id
        FROM task
        WHERE run_at <= $1 AND started_at IS NULL
        ORDER BY run_at
        LIMIT 1
        FOR UPDATE SKIP LOCKED
        """,
        now or datetime.now(UTC),
    )


async def task_started(*, task_id: int) -> None:
    """
    Set the time when the task started executing.
    """

    await db.execute(
        "UPDATE task SET started_at=clock_timestamp() WHERE id = $1", task_id
    )


async def task_finished(*, task_id: int) -> None:
    """
    Set the time when the task finished.
    """

    await db.execute(
        "UPDATE task SET finished_at=clock_timestamp() WHERE id = $1", task_id
    )


async def task_failed(*, task_id: int) -> None:
    """
    Reset task state and increase run-at by 30 seconds.
    """

    await db.execute(
        """
        UPDATE task SET started_at=NULL, run_at=run_at + '30 seconds'::interval
        WHERE id = $1
        """,
        task_id,
    )


###################
# Scheduled tasks #
###################


@db.transaction()
async def create_scheduled_task(
    *, name: str, arguments: dict[str, Any], cron_expression: str
) -> int:
    """
    Create a scheduled task and queue it's next execution.
    """

    schedule_id: int = await db.fetchval(
        """
        INSERT INTO scheduled_task (name, arguments, expression, is_enabled)
        VALUES ($1, $2, $3, false)
        RETURNING id;
        """,
        name,
        arguments,
        cron_expression,
    )

    run_at = croniter(cron_expression, datetime.now(UTC)).get_next(datetime)

    task_id: int = await db.fetchval(
        """
        INSERT INTO task (name, arguments, from_schedule_id, run_at)
        VALUES ($1, $2, $3, $4)
        RETURNING id
        """,
        name,
        arguments,
        schedule_id,
        run_at,
    )

    await db.execute(
        "UPDATE scheduled_task SET next_task_id=$1, is_enabled=true WHERE id = $2",
        task_id,
        schedule_id,
    )

    return schedule_id


@db.transaction()
async def queue_next_task(
    *, schedule_id: int, previous: datetime | None = None
) -> None:
    task = await db.fetchrow(
        "SELECT name, arguments, expression FROM scheduled_task WHERE id = $1",
        schedule_id,
    )
    if task is None:
        raise ValueError(f"No such schedule: {schedule_id}")

    name, arguments, cron_expression = task

    previous = previous or datetime.now(UTC)
    run_at = croniter(cron_expression, previous).get_next(datetime)

    task_id: int = await db.fetchval(
        """
        INSERT INTO task (name, arguments, from_schedule_id, run_at)
        VALUES ($1, $2, $3, $4)
        RETURNING id
        """,
        name,
        arguments,
        schedule_id,
        run_at,
    )

    await db.execute(
        "UPDATE scheduled_task SET next_task_id=$1 WHERE id = $2",
        task_id,
        schedule_id,
    )
