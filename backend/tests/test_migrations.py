"""Check that the migrations build the same tables the models describe, and can be undone."""

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg

from tests.conftest import TEST_DB_URL

BACKEND = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = {
    "users",
    "api_tokens",
    "audit_log",
    "page_members",
    "page_invites",
    "share_links",
    "blobs",
    "pages",
    "page_versions",
    "version_files",
    "comments",
    "revision_requests",
    "alembic_version",
}


def _with_database(url: str, name: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{name}", parts.query, ""))


def _alembic(url: str, *args: str) -> None:
    env = {**os.environ, "DATABASE_URL": url, "DATABASE_URL_UNPOOLED": url}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


async def _tables(url: str) -> set[str]:
    conn = await asyncpg.connect(url)
    try:
        rows = await conn.fetch("select tablename from pg_tables where schemaname = 'public'")
        return {r["tablename"] for r in rows}
    finally:
        await conn.close()


async def test_migrations_upgrade_and_downgrade():
    admin = await asyncpg.connect(TEST_DB_URL)
    await admin.execute("drop database if exists paddock_migration_check")
    await admin.execute("create database paddock_migration_check")
    await admin.close()

    url = _with_database(TEST_DB_URL, "paddock_migration_check")
    _alembic(url, "upgrade", "head")
    assert EXPECTED_TABLES <= await _tables(url)

    _alembic(url, "downgrade", "base")
    assert (await _tables(url)) - {"alembic_version"} == set()

    admin = await asyncpg.connect(TEST_DB_URL)
    await admin.execute("drop database paddock_migration_check")
    await admin.close()
