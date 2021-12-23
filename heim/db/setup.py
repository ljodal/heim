"""
Helpers to set up the database
"""

from pathlib import Path

import asyncpg  # type: ignore

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


async def migrate_db() -> None:
    con = await asyncpg.connect()

    try:
        await create_migrations_table(con=con)
        applied_migrations = await get_applied_migrations(con=con)
        for migrations_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if migrations_file.stem not in applied_migrations:
                await apply_migration(path=migrations_file, con=con)
    finally:
        await con.close()


async def create_migrations_table(*, con: asyncpg.Connection) -> None:
    await con.execute(
        """
        create table if not exists migrations (
            name varchar primary key,
            applied_at timestamp with time zone not null
        );
        """
    )


async def get_applied_migrations(*, con: asyncpg.Connection) -> list[str]:
    return [row["name"] for row in await con.fetch("SELECT name FROM migrations")]


async def apply_migration(*, path: Path, con: asyncpg.Connection) -> None:
    name = path.stem
    await con.execute(
        "INSERT INTO MIGRATIONS (name, applied_at) VALUES ($1, now())", name
    )
    await con.execute(path.read_text())
