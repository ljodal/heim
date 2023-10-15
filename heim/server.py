import os
from importlib import import_module
from pathlib import Path

import sentry_sdk
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from sentry_sdk.integrations.asyncpg import AsyncPGIntegration

from . import db

sentry_sdk.init(
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
    integrations=[
        AsyncPGIntegration(),
    ],
    debug="DEBUG" in os.environ,
)

app = FastAPI()

Instrumentator().instrument(app).expose(app)


def load_apps(path: Path) -> None:
    for api_module in path.glob("*/api.py"):
        # Construct the name of the module
        relative_path = api_module.relative_to(Path(__file__).parent)
        module_path = ".".join(p.name for p in reversed(relative_path.parents))
        module_name = f"{module_path}.{api_module.stem}"

        # Register the module
        module = import_module(module_name, package="heim")
        if router := getattr(module, "router", None):
            app.include_router(router, prefix="/api")


load_apps(Path(__file__).parent)
load_apps(Path(__file__).parent / "integrations")


@app.on_event("startup")
async def startup() -> None:
    await db.connect()


@app.on_event("shutdown")
async def shutdown() -> None:
    await db.disconnect()


@app.get("/health")
async def get_health() -> dict[str, str]:
    await db.fetch("SELECT 1")
    return {"status": "pass"}


@app.get("/sentry-debug")
async def trigger_error() -> None:
    1 / 0
