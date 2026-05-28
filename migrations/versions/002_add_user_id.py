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
    # Add user_id with the deterministic dev UUID as the server default so any
    # pre-existing local rows are attributable to the dev user rather than an
    # invalid empty string.  Production DB is always empty at migration time so
    # the default is never applied to real user rows.
    op.add_column(
        "expenses",
        sa.Column(
            "user_id",
            sa.String(),
            nullable=False,
            server_default="00000000-0000-0000-0000-000000000001",
        ),
    )
    op.create_index("ix_expenses_user_id", "expenses", ["user_id"])
    # Drop the server_default after the backfill so that future inserts must
    # explicitly supply user_id rather than silently falling back to the dev UUID.
    with op.batch_alter_table("expenses", schema=None) as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.String(), server_default=None)


def downgrade() -> None:
    op.drop_index("ix_expenses_user_id", table_name="expenses")
    op.drop_column("expenses", "user_id")
