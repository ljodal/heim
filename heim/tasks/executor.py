import asyncio
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import ParamSpec, TypeVar

import structlog

from .. import db
from .base import Task, get_task
from .queries import (
    get_next_task,
    queue_next_task,
    task_failed,
    task_finished,
    task_started,
)

logger = structlog.get_logger()

P = ParamSpec("P")
R = TypeVar("R")


def load_tasks() -> None:
    def _load_tasks(path: Path) -> None:
        for api_module in path.glob("*/tasks.py"):
            # Construct the name of the module
            relative_path = api_module.relative_to(Path(__file__).parent.parent)
            module_path = ".".join(p.name for p in reversed(relative_path.parents))
            module_name = f"{module_path}.{api_module.stem}"

            # Import the module
            import_module(module_name, package="heim")

    _load_tasks(Path(__file__).parent.parent)
    _load_tasks(Path(__file__).parent.parent / "integrations")


async def run_tasks() -> None:
    """
    Loop forever executing tasks.
    """

    while True:
        if not await run_next_task():
            await asyncio.sleep(1)


async def run_next_task() -> bool:
    """
    Run the next pending task.
    """

    async with db.transaction():
        if _task := await get_next_task():
            task_id, name, arguments, run_at, from_schedule_id = _task
            logger.info(
                "Executing task",
                task_id=task_id,
                task_name=name,
                task_arguments=arguments,
            )
            task = get_task(name=name)
            await task_started(task_id=task_id)

            if task.atomic:
                await asyncio.shield(
                    execute_task(
                        task=task,
                        task_id=task_id,
                        arguments=arguments,
                        run_at=run_at,
                        from_schedule_id=from_schedule_id,
                        atomic=True,
                    )
                )

    if _task and not task.atomic:
        await asyncio.shield(
            execute_task(
                task=task,
                task_id=task_id,
                arguments=arguments,
                run_at=run_at,
                from_schedule_id=from_schedule_id,
                atomic=False,
            )
        )

        return True

    return False


async def execute_task(
    *,
    task: Task[P, R],
    task_id: int,
    arguments: P.kwargs,
    run_at: datetime,
    from_schedule_id: int | None,
    atomic: bool,
) -> None:
    """
    Execute a single task.
    """

    try:
        if atomic:
            async with db.transaction():
                await asyncio.wait_for(task(**arguments), timeout=task.timeout)
        else:
            await asyncio.wait_for(task(**arguments), timeout=task.timeout)
        logger.info(
            "Task finished",
            task_id=task_id,
            task_name=task.name,
            task_arguments=arguments,
        )
    except Exception:
        logger.exception(
            "Task failed",
            task_id=task_id,
            task_name=task.name,
            task_arguments=arguments,
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
