from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Expense
from app.schemas import CategoryTotal, MonthTotal


def total_by_month(db: Session) -> list[MonthTotal]:
    """Return total spend per calendar month, sorted ascending by month string."""
    # strftime("%Y-%m", ...) is SQLite-specific; gives a sortable "YYYY-MM" key
    month_key = func.strftime("%Y-%m", Expense.occurred_at).label("month")
    stmt = (
        select(month_key, func.sum(Expense.amount).label("total"))
        .group_by(month_key)
        .order_by(month_key.asc())
    )
    rows = db.execute(stmt).all()
    return [MonthTotal(month=row.month, total=float(row.total)) for row in rows]


def total_by_category(db: Session) -> list[CategoryTotal]:
    """Return total spend per category, sorted by total descending then category ascending."""
    stmt = (
        select(Expense.category, func.sum(Expense.amount).label("total"))
        .group_by(Expense.category)
        .order_by(func.sum(Expense.amount).desc(), Expense.category.asc())
    )
    rows = db.execute(stmt).all()
    return [CategoryTotal(category=row.category, total=float(row.total)) for row in rows]
