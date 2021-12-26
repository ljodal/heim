from importlib import import_module
from pathlib import Path

from fastapi import FastAPI

from . import db

app = FastAPI()


def load_apps(path: Path) -> None:
    for api_module in path.glob("*/api.py"):

        # Construct the name of the module
        relative_path = api_module.relative_to(Path(__file__).parent)
        module_path = ".".join(p.name for p in reversed(relative_path.parents))
        module_name = f"{module_path}.{api_module.stem}"

        # Register the module
        module = import_module(module_name, package="heim")
        if router := getattr(module, "router", None):
            app.include_router(router)


load_apps(Path(__file__).parent)
load_apps(Path(__file__).parent / "integrations")


@app.on_event("startup")
async def startup():
    await db.connect()


@app.on_event("shutdown")
async def shutdown():
    await db.disconnect()


@app.get("/health")
async def get_health() -> dict:
    await db.fetch("SELECT 1")
    return {"status": "pass"}
