#!/usr/bin/env python3
"""
Apply the given migration.
"""

import argparse
import asyncio
import logging
from importlib import import_module
from pathlib import Path

import structlog

from heim import db
from heim.tasks.executor import run_tasks

structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)

parser = argparse.ArgumentParser(description="Execute background tasks")
parser.add_argument("--num-workers", help="Number of workers to run", default=1)

args = parser.parse_args()


def load_tasks(path: Path) -> None:
    for api_module in path.glob("*/tasks.py"):
        # Construct the name of the module
        relative_path = api_module.relative_to(Path(__file__).parent.parent / "heim")
        module_path = ".".join(p.name for p in reversed(relative_path.parents))
        module_name = f"{module_path}.{api_module.stem}"

        # Import the module
        import_module(module_name, package="heim")


load_tasks(Path(__file__).parent.parent / "heim")
load_tasks(Path(__file__).parent.parent / "heim" / "integrations")


@db.setup_pool()
async def main(num_workers: int) -> None:
    await asyncio.gather(*(run_tasks() for _ in range(num_workers)))


try:
    asyncio.run(main(args.num_workers))
except KeyboardInterrupt:
    pass
