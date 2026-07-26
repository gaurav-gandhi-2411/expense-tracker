"""app_profiles — records which Supabase-authenticated users have used this app

Wave 15 (gg-portfolio): this project's Postgres now lives inside review-iq's
Supabase project (shared free-tier constraint) and both apps share one
Supabase Auth (auth.users) namespace. See app.models.AppProfile.

Revision ID: 003
Revises: 002
Create Date: 2026-07-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_profiles",
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column(
            "first_seen_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("app_profiles")
