from .base import task
from .queries import delete_old_tasks as delete_old_tasks_query


@task(name="delete-old-tasks", allow_skip=True)
async def delete_old_tasks() -> None:
    """
    Delete tasks that have been run in the past
    """

    await delete_old_tasks_query()
