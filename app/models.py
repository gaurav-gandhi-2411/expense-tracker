from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AppProfile(Base):
    """Records that a Supabase-authenticated user has actually used this app.

    Wave 15 (gg-portfolio) — this project's Supabase Postgres now lives in
    review-iq's project (both share one Supabase Auth `auth.users` namespace,
    a free-tier project-count constraint). A row here is created the first
    time a given auth user_id calls any endpoint here — it doesn't gate
    access (this app never gated access before sharing a project either),
    but it makes "who has actually touched expense-tracker" an explicit,
    queryable fact instead of an implicit one, and gives a real place to
    add an allowlist/invite gate later without a schema change.
    """

    __tablename__ = "app_profiles"

    user_id: Mapped[str] = mapped_column(primary_key=True)
    first_seen_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    amount: Mapped[float] = mapped_column(nullable=False)
    category: Mapped[str] = mapped_column(nullable=False, index=True)
    description: Mapped[str] = mapped_column(nullable=False, default="")
    occurred_at: Mapped[date] = mapped_column(nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    user_id: Mapped[str] = mapped_column(nullable=False, index=True, default="")
