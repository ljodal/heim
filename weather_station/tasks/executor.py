import asyncio
from datetime import datetime, timezone

import structlog

from .. import db
from .base import get_task
from .queries import (
    get_next_task,
    queue_next_task,
    task_failed,
    task_finished,
    task_started,
)

logger = structlog.get_logger()


async def run_tasks() -> None:
    """
    Loop forever executing tasks.
    """

    while True:
        if not await run_next_task():
            await asyncio.sleep(1)

        return


@db.transaction()
async def run_next_task() -> bool:
    """
    Run the next pending task.
    """

    if _task := await get_next_task():
        task_id, name, arguments, run_at, from_schedule_id = _task
        logger.info("Executing task", task_id=task_id, task_name=name)
        task = get_task(name=name)
        await task_started(task_id=task_id)
        try:
            async with db.transaction():
                await task(**arguments)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "Task failed, resetting state", task_id=task_id, task_name=name
            )
            await task_failed(task_id=task_id)
        else:
            await task_finished(task_id=task_id)
            if from_schedule_id:
                await queue_next_task(
                    schedule_id=from_schedule_id,
                    previous=(
                        run_at if not task.allow_skip else datetime.now(timezone.utc)
                    ),
                )

        return True

    return False
