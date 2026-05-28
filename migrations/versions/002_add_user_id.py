"""add user_id column and index (Phase 3a multi-user isolation)

Revision ID: 002
Revises: 001
Create Date: 2026-05-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "expenses",
        sa.Column("user_id", sa.String(), nullable=False, server_default=""),
    )
    op.create_index("ix_expenses_user_id", "expenses", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_expenses_user_id", table_name="expenses")
    op.drop_column("expenses", "user_id")
