from datetime import datetime
from typing import Any, Awaitable, Callable, Optional, Protocol, TypeVar, cast

from .queries import schedule_task

T = TypeVar("T", bound=Callable[..., Awaitable[Any]])


class Task(Protocol):
    def __call__(self, *args, **kwargs) -> Awaitable[Any]:
        ...

    async def schedule(
        self, *, arguments: dict[str, Any], run_at: Optional[datetime] = ...
    ) -> int:
        ...


_TASK_REGISTRY: dict[str, Task] = {}


async def call_task(*, name: str, arguments: dict[str, Any]) -> None:
    """
    Call a task by name.
    """

    _task = _TASK_REGISTRY[name]
    await _task(**arguments)


def task(*, name: str) -> Callable[[T], T]:
    """
    Decorator for declaring a task that can be executed in the background.
    """

    async def schedule(
        *, arguments: dict[str, Any], run_at: Optional[datetime] = None
    ) -> int:
        """
        Schedule the task for execution at a later time.
        """

        return await schedule_task(name=name, arguments=arguments, run_at=run_at)

    def _inner(func: T) -> T:
        assert name not in _TASK_REGISTRY
        _TASK_REGISTRY[name] = cast(Task, func)
        func.schedule = schedule  # type: ignore
        return func

    return _inner
