from collections.abc import Awaitable, Callable, Generator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generic, ParamSpec, TypeVar
from warnings import warn

from .queries import create_scheduled_task, queue_task

P = ParamSpec("P")
R = TypeVar("R")


@dataclass(kw_only=True)
class BoundTask(Generic[R]):
    """A task with bound arguments, ready to be scheduled or deferred."""

    name: str
    arguments: dict[str, Any]
    func: Callable[..., Awaitable[R]]
    _consumed: bool = field(default=False, repr=False)

    def __del__(self) -> None:
        if not self._consumed:
            warn(
                f"PreparedTask '{self.name}' was never awaited or scheduled",
                RuntimeWarning,
                stacklevel=2,
            )

    def __await__(self) -> Generator[Any, None, R]:
        self._consumed = True
        return self.func(**self.arguments).__await__()

    async def defer(self, *, run_at: datetime | None = None) -> int:
        self._consumed = True
        return await queue_task(name=self.name, arguments=self.arguments, run_at=run_at)

    async def schedule(self, *, cron_expression: str) -> int:
        self._consumed = True
        return await create_scheduled_task(
            name=self.name, arguments=self.arguments, cron_expression=cron_expression
        )


@dataclass(frozen=True, kw_only=True)
class Task(Generic[P, R]):
    func: Callable[P, Awaitable[R]]
    name: str
    allow_skip: bool
    atomic: bool
    timeout: int

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> BoundTask[R]:
        return BoundTask(name=self.name, arguments=kwargs, func=self.func)


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
