import asyncio
import inspect
import os
from collections.abc import Callable
from importlib import import_module
from pathlib import Path
from typing import Any

import click
import sentry_sdk
from sentry_sdk.integrations.asyncpg import AsyncPGIntegration

if os.environ.get("SENTRY_DSN"):
    sentry_sdk.init(
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
        integrations=[
            AsyncPGIntegration(),
        ],
        debug="DEBUG" in os.environ,
    )


class AsyncAwareContext(click.Context):
    """
    A click context that invokes async functions with asyncio.run.
    """

    def invoke(self, __callback: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        r = super().invoke(__callback, *args, **kwargs)
        if inspect.iscoroutine(r):
            return asyncio.run(r)
        else:
            return r


click.Command.context_class = AsyncAwareContext
click.Group.context_class = AsyncAwareContext


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
