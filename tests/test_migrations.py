"""Verify that running alembic upgrade head on a fresh DB produces the expected schema."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def alembic_config(tmp_path):
    from alembic.config import Config

    db_path = tmp_path / "test_migrations.db"
    cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def test_upgrade_head_creates_expenses_table(alembic_config) -> None:
    from alembic import command
    from sqlalchemy import create_engine, inspect

    command.upgrade(alembic_config, "head")

    engine = create_engine(alembic_config.get_main_option("sqlalchemy.url"))
    inspector = inspect(engine)

    assert "expenses" in inspector.get_table_names()

    columns = {col["name"] for col in inspector.get_columns("expenses")}
    expected = {"id", "amount", "category", "description", "occurred_at", "created_at", "user_id"}
    assert expected.issubset(columns), f"Missing columns: {expected - columns}"
    engine.dispose()


def test_upgrade_head_creates_user_id_index(alembic_config) -> None:
    from alembic import command
    from sqlalchemy import create_engine, inspect

    command.upgrade(alembic_config, "head")

    engine = create_engine(alembic_config.get_main_option("sqlalchemy.url"))
    inspector = inspect(engine)

    indexes = inspector.get_indexes("expenses")
    index_names = {idx["name"] for idx in indexes}
    assert any("user_id" in name for name in index_names), (
        f"No user_id index found. Indexes: {index_names}"
    )
    engine.dispose()


def test_downgrade_base_then_upgrade_head_is_idempotent(alembic_config) -> None:
    from alembic import command
    from sqlalchemy import create_engine, inspect

    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")

    engine = create_engine(alembic_config.get_main_option("sqlalchemy.url"))
    inspector = inspect(engine)

    assert "expenses" in inspector.get_table_names()
    columns = {col["name"] for col in inspector.get_columns("expenses")}
    assert "user_id" in columns
    engine.dispose()
