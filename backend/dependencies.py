"""
FastAPI dependencies: the bridge between the web layer and db/.

get_db() is a generator dependency - FastAPI calls it, gets the
yielded Session, injects it into the route function, and once the
route returns (success OR exception) resumes the generator so the
`finally` block runs and the session is always closed. This is the
standard "one Session per request" pattern: each HTTP request gets
its own isolated database session, closed automatically at the end of
that request, so leaked/shared connections never build up.
"""

from __future__ import annotations

from typing import Iterator

from sqlalchemy.orm import Session

from db.base import SessionLocal


def get_db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
