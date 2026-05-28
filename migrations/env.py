from __future__ import annotations

from alembic import context
from sqlalchemy import create_engine, pool

import app.models  # noqa: F401 — registers Expense with Base.metadata
from app.db import Base

config = context.config
target_metadata = Base.metadata


def get_url() -> str:
    """Resolve DB URL: alembic.ini override → app settings → SQLite fallback."""
    url = config.get_main_option("sqlalchemy.url") or ""
    if url:
        return url
    try:
        from app.config import get_settings

        return get_settings().database_url
    except Exception:
        return "sqlite:///./expense_tracker.db"


def run_migrations_offline() -> None:
    """Emit SQL without a live DB connection (used with --sql flag)."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB connection."""
    url = get_url()
    connectable = create_engine(url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
