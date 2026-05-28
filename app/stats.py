from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Expense
from app.schemas import CategoryTotal, MonthTotal


def total_by_month(db: Session, user_id: str) -> list[MonthTotal]:
    """Return total spend per calendar month, sorted ascending by month string.

    Groups in Python rather than SQL so the query works identically on SQLite and Postgres.
    """
    stmt = select(Expense.occurred_at, Expense.amount).where(Expense.user_id == user_id)
    rows = db.execute(stmt).all()
    totals: dict[str, float] = defaultdict(float)
    for row in rows:
        key = row.occurred_at.strftime("%Y-%m")
        totals[key] += row.amount
    return sorted(
        [MonthTotal(month=k, total=v) for k, v in totals.items()],
        key=lambda x: x.month,
    )


def total_by_category(db: Session, user_id: str) -> list[CategoryTotal]:
    """Return total spend per category, sorted by total descending then category ascending.

    Groups in Python rather than SQL so the query works identically on SQLite and Postgres.
    """
    stmt = select(Expense.category, Expense.amount).where(Expense.user_id == user_id)
    rows = db.execute(stmt).all()
    totals: dict[str, float] = defaultdict(float)
    for row in rows:
        totals[row.category] += row.amount
    return sorted(
        [CategoryTotal(category=k, total=v) for k, v in totals.items()],
        key=lambda x: (-x.total, x.category),
    )
