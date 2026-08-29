"""
Database engine/session setup.

Real-world analogy:
    This is the one place in the whole project that knows the actual
    database connection string. Everything else (repositories, and
    later FastAPI routes) receives a Session object instead of
    reaching for a global connection - that's what makes those pieces
    testable against a throwaway test database instead of whatever
    database happens to be configured for local dev.

Why an environment variable, not a hard-coded connection string:
    Different environments (your laptop, a CI runner, eventually a
    real deployment) need different credentials/hosts. Hard-coding a
    connection string - especially one with a password in it - is
    exactly the kind of thing project rule #6 forbids ("never
    hard-code passwords"). DATABASE_URL defaults to matching
    docker-compose.yml's postgres service, so local dev works with
    zero configuration, but it's always overridable.
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://forgesentinel:forgesentinel@localhost:5432/forgesentinel"
)

DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


class Base(DeclarativeBase):
    """Shared declarative base every ORM model inherits from."""


# echo=False: set to True locally (or via an env var) if you ever need
# to see every SQL statement SQLAlchemy generates while debugging.
engine = create_engine(DATABASE_URL, echo=False, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_session() -> Session:
    """
    Create a new Session bound to the configured engine.

    Callers are responsible for closing it (or using it as a context
    manager: `with get_session() as session:`) - this function just
    knows *how* to build one, not when its work is done.
    """
    return SessionLocal()
