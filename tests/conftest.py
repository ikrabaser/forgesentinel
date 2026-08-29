"""
Shared pytest fixtures for database-backed tests.

Why tests use Base.metadata.create_all() instead of running Alembic
migrations:
    Alembic exists to evolve a *real, persistent* database's schema
    safely over time, one incremental step at a time - that's a
    concern about production deployments. A test database is
    disposable and recreated fresh; it just needs *a* schema that
    matches the current models right now, so building it directly
    from Base.metadata is faster and has nothing to keep in sync.
    Alembic's migration history remains the source of truth for how a
    real deployment's database got to its current shape.

Why a separate database (forgesentinel_test), not the dev database:
    Tests insert and delete rows freely. Sharing the same database
    used for manual/dev testing would make test runs clobber whatever
    data you were just looking at - and a test failing to clean up
    could quietly corrupt your dev session's data too.
"""

from __future__ import annotations

import os

import psycopg
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from db.base import Base, DATABASE_URL

TEST_DATABASE_NAME = "forgesentinel_test"


def _admin_connection_string() -> str:
    """Connection string to the 'postgres' maintenance database, used
    only to issue CREATE DATABASE (which can't run inside a
    transaction against the database being created)."""
    base = DATABASE_URL.rsplit("/", 1)[0]
    return f"{base}/postgres"


def _test_database_url() -> str:
    base = DATABASE_URL.rsplit("/", 1)[0]
    return f"{base}/{TEST_DATABASE_NAME}"


@pytest.fixture(scope="session")
def test_engine():
    admin_url = _admin_connection_string().replace("postgresql+psycopg://", "postgresql://")
    try:
        with psycopg.connect(admin_url, autocommit=True, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DATABASE_NAME,)
                )
                if cur.fetchone() is None:
                    cur.execute(f"CREATE DATABASE {TEST_DATABASE_NAME}")
    except psycopg.OperationalError as exc:
        pytest.skip(
            f"PostgreSQL not reachable at {admin_url} ({exc}); "
            "start it with `docker compose up -d` to run DB-backed tests"
        )

    engine = create_engine(_test_database_url(), future=True)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(test_engine):
    """
    One Session per test, with all tables truncated first so every
    test starts from a known-empty state regardless of what earlier
    tests inserted.
    """
    with test_engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE'))

    session_factory = sessionmaker(bind=test_engine, future=True)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
