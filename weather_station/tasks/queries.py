from datetime import datetime, timezone
from typing import Any, Optional

from croniter import croniter

from .. import db


async def schedule_task(
    *, name: str, arguments: dict[str, Any], run_at: datetime | None
) -> int:
    """
    Schedule a task to run at the given time.
    """

    return await db.fetchval(
        """
        INSERT INTO task (name, arguments, run_at)
        VALUES ($1, $2, $3) RETURNING id;
        """,
        name,
        arguments,
        run_at or datetime.now(timezone.utc),
    )


async def get_next_task() -> tuple[
    int, str, dict[str, Any], datetime, Optional[int]
] | None:
    """
    Get and lock the next pending task. Must be called from within a
    transaction.
    """

    return await db.fetchrow(
        """
        SELECT id, name, arguments, from_schedule_id
        FROM task
        WHERE run_at <= now() AND started_at IS NULL
        ORDER BY run_at
        FOR UPDATE SKIP LOCKED
        """
    )


async def task_started(*, task_id: int) -> None:
    await db.execute(
        "UPDATE task SET started_at=clock_timestamp() WHERE id = $1", task_id
    )


async def task_finished(*, task_id: int) -> None:
    await db.execute(
        "UPDATE task SET finished_at=clock_timestamp()() WHERE id = $1", task_id
    )


async def task_failed(*, task_id: int) -> None:
    await db.execute("UPDATE task SET started_at=NULL WHERE id = $1", task_id)


###################
# Scheduled tasks #
###################


@db.transaction()
async def schedule_next_task(*, schedule_id: int, previous: datetime) -> None:

    name, arguments, cron_expression = await db.fetchrow(
        "SELECT name, arguments, expression FROM scheduled_task WHERE id = $1",
        schedule_id,
    )

    run_at = croniter(cron_expression, previous).get_next(datetime)

    task_id: int = await db.fetchval(
        """
        INSERT INTO task (name, arguments, from_schedule_id, run_at)
        VALUES ($1, $2, $3, $4)
        RETURNING id
        """,
        run_at,
        schedule_id,
    )

    await db.execute(
        "UPDATE scheduled_task SET next_task_id=$1 WHERE id = $2",
        task_id,
        schedule_id,
    )
