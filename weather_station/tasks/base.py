from datetime import datetime
from typing import Any, Awaitable, Callable, Optional, Protocol, TypeVar, cast

from .queries import create_scheduled_task, queue_task

T = TypeVar("T", bound=Callable[..., Awaitable[Any]])


class Task(Protocol):

    name: str
    allow_skip: bool

    def __call__(self, *args, **kwargs) -> Awaitable[Any]:
        ...

    async def defer(
        self, *, arguments: dict[str, Any], run_at: Optional[datetime] = ...
    ) -> int:
        ...

    async def schedule(self, *, arguments: dict[str, Any], cron_expression: str) -> int:
        ...


_TASK_REGISTRY: dict[str, Task] = {}


def get_task(*, name: str) -> Task:
    """
    Get a task by name
    """

    return _TASK_REGISTRY[name]


def task(*, name: str, allow_skip: bool = False) -> Callable[[T], T]:
    """
    Decorator for declaring a task that can be executed in the background.
    """

    async def defer(
        *, arguments: dict[str, Any], run_at: Optional[datetime] = None
    ) -> int:
        """
        Schedule the task for execution at a later time.
        """

        return await queue_task(name=name, arguments=arguments, run_at=run_at)

    async def schedule(*, arguments: dict[str, Any], cron_expression: str) -> int:
        """
        Create a schedule to execute this task.
        """

        return await create_scheduled_task(
            name=name, arguments=arguments, cron_expression=cron_expression
        )

    def _inner(func: T) -> T:
        assert name not in _TASK_REGISTRY
        _TASK_REGISTRY[name] = cast(Task, func)
        func.defer = defer  # type: ignore
        func.schedule = schedule  # type: ignore
        func.name = name  # type: ignore
        func.allow_skip = (allow_skip,)  # type: ignore
        return func

    return _inner
