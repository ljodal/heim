import asyncio

import structlog

from .. import db
from .base import call_task
from .queries import (
    get_next_task,
    schedule_next_task,
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


@db.transaction()
async def run_next_task() -> bool:
    """
    Run the next pending task.
    """

    if task := await get_next_task():
        task_id, name, arguments, run_at, from_schedule_id = task
        await task_started(task_id=task_id)
        try:
            async with db.transaction():
                await call_task(name=name, arguments=arguments)
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
                await schedule_next_task(schedule_id=from_schedule_id, previous=run_at)

        return True

    return False
