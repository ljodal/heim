import asyncio

import click

from .. import db
from .executor import load_tasks, run_tasks


@click.group(name="tasks")
def cli() -> None:
    load_tasks()


@cli.command(help="Run the task runner")
@click.option(
    "--num-workers", type=int, default=1, help="Number of worker tasks to run"
)
@db.setup_pool()
async def run(*, num_workers: int) -> None:
    await asyncio.gather(*(run_tasks() for _ in range(num_workers)))
