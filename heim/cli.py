import asyncio
import inspect
import logging
from importlib import import_module
from pathlib import Path

import click
import structlog

structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)


class AsyncAwareContext(click.Context):
    """
    A click context that invokes async functions with asyncio.run.
    """

    def invoke(self, *args, **kwargs):
        r = super().invoke(*args, **kwargs)
        if inspect.isawaitable(r):
            return asyncio.run(r)
        else:
            return r


click.BaseCommand.context_class = AsyncAwareContext


@click.group()
def cli() -> None:
    pass


def load_apps(path: Path) -> None:
    for api_module in path.glob("*/cli*.py"):

        # Construct the name of the module
        relative_path = api_module.relative_to(Path(__file__).parent)
        module_path = ".".join(p.name for p in reversed(relative_path.parents))
        module_name = f"{module_path}.{api_module.stem}"

        # Register the module
        module = import_module(module_name, package="heim")
        if command := getattr(module, "cli", None):
            cli.add_command(command)


load_apps(Path(__file__).parent)
load_apps(Path(__file__).parent / "integrations")
