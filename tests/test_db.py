"""
Basic tests to ensure that the database logic works.
"""

import pytest

from heim import db

pytestmark = pytest.mark.asyncio


async def test_fetch(connection: None) -> None:
    rows = await db.fetch("SELECT * FROM generate_series(1, 2)")
    assert len(rows) == 2
    assert len(rows[0]) == 1
    assert rows[0][0] == 1
    assert rows[1][0] == 2


async def test_fetchrow(connection: None) -> None:
    row = await db.fetchrow("SELECT 1, 'Hello'")
    assert row
    assert len(row) == 2
    assert row[0] == 1
    assert row[1] == "Hello"


async def test_fetchval(connection: None) -> None:
    result: int = await db.fetchval("SELECT 1")
    assert result == 1
