"""
Helpers to set up the database
"""

from __future__ import annotations

from pathlib import Path

import asyncpg

from .. import db

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


@db.setup()
async def migrate_db() -> None:
    async with db.connection() as con:
        await create_migrations_table(con=con)
        applied_migrations = await get_applied_migrations(con=con)
        for migrations_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if migrations_file.stem not in applied_migrations:
                await apply_migration(path=migrations_file, con=con)


async def create_migrations_table(*, con: asyncpg.Connection[asyncpg.Record]) -> None:
    await con.execute(
        """
        create table if not exists migrations (
            name varchar primary key,
            applied_at timestamp with time zone not null
        );
        """
    )


async def get_applied_migrations(
    *, con: asyncpg.Connection[asyncpg.Record]
) -> list[str]:
    return [row["name"] for row in await con.fetch("SELECT name FROM migrations")]


async def apply_migration(
    *, path: Path, con: asyncpg.Connection[asyncpg.Record]
) -> None:
    name = path.stem

    print(f"Applying migration {name}")

    await con.execute(
        "INSERT INTO MIGRATIONS (name, applied_at) VALUES ($1, now())", name
    )
    await con.execute(path.read_text())
