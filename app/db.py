from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool


def _make_engine():
    from app.config import get_settings

    url = get_settings().database_url
    if url.startswith("sqlite"):
        # check_same_thread=False required for FastAPI's threaded request handling.
        return create_engine(url, connect_args={"check_same_thread": False})
    # Postgres/Supabase: NullPool avoids pgBouncer pooler incompatibilities on free tier.
    return create_engine(url, poolclass=NullPool)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session and closes it on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
