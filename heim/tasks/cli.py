import asyncio

import click

from .. import db
from .executor import load_tasks, run_tasks
from .queries import get_tasks


@click.group(name="tasks", help="Run and inspect background tasks")
def cli() -> None:
    load_tasks()


@cli.command(help="Run the task runner")
@click.option(
    "--num-workers", type=int, default=1, help="Number of worker tasks to run"
)
@db.setup_pool()
async def run(*, num_workers: int) -> None:
    await asyncio.gather(*(run_tasks() for _ in range(num_workers)))


@cli.command(name="list", help="List pending tasks")
@click.option("--all", "show_all", is_flag=True, help="List all tasks")
@db.setup()
async def list_tasks(show_all: bool) -> None:
    rows: list[tuple[str, str, str, str, str]] = [
        ("Task ID", "Name", "Arguments", "Run at", "Schedule ID")
    ]
    rows.extend(
        (str(task_id), name, str(arguments), run_at.isoformat(), str(from_schedule_id))
        for task_id, name, arguments, run_at, from_schedule_id in await get_tasks(
            show_all=show_all
        )
    )

    column_lengths = [
        max(len(row[column]) for row in rows) for column in range(len(rows[0]))
    ]

    for columns in rows:
        click.echo(
            " | ".join(
                column.ljust(column_lengths[i]) for i, column in enumerate(columns)
            )
        )
