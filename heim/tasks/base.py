from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable, Generic, Optional, ParamSpec, TypeVar

from .queries import create_scheduled_task, queue_task

P = ParamSpec("P")
R = TypeVar("R")


@dataclass(frozen=True, kw_only=True)
class Task(Generic[P, R]):
    func: Callable[P, Awaitable[R]]
    name: str
    allow_skip: bool
    atomic: bool
    timeout: int

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> Awaitable[R]:
        return self.func(*args, **kwargs)

    async def defer(
        self, *, arguments: P.kwargs, run_at: Optional[datetime] = None
    ) -> int:
        return await queue_task(name=self.name, arguments=arguments, run_at=run_at)

    async def schedule(self, *, arguments: P.kwargs, cron_expression: str) -> int:
        return await create_scheduled_task(
            name=self.name, arguments=arguments, cron_expression=cron_expression
        )


_TASK_REGISTRY: dict[str, Task[Any, Any]] = {}


def get_task(*, name: str) -> Task[Any, Any]:
    """
    Get a task by name
    """

    return _TASK_REGISTRY[name]


def task(
    *, name: str, allow_skip: bool = False, atomic: bool = True, timeout: int = 10
) -> Callable[[Callable[P, Awaitable[R]]], Task[P, R]]:
    """
    Decorator for declaring a task that can be executed in the background.

    :param name:       A unique name for this task
    :param allow_skip: Allow schedule steps to be skipped
    :param atomic:     Run the task fully atomically in a transaction
    :param timeout:    The maximum time to allow the task to execute for
    """

    def _inner(func: Callable[P, Awaitable[R]]) -> Task[P, R]:
        assert name not in _TASK_REGISTRY
        task = Task(
            func=func,
            name=name,
            allow_skip=allow_skip,
            atomic=atomic,
            timeout=timeout,
        )
        _TASK_REGISTRY[name] = task
        return task

    return _inner
