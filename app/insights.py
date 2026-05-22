from __future__ import annotations

import re
from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm import LLMClient
from app.models import Expense
from app.schemas import Insight

# ---------------------------------------------------------------------------
# Prompt templates — each is well under 1500 chars after substitution.
# ---------------------------------------------------------------------------

_MONTHLY_SYSTEM = (
    "You are a personal finance assistant. Given spending statistics for a calendar month, "
    "write a brief analytical summary.\n"
    "Rules: Write 2-3 short paragraphs of plain prose. No markdown formatting, no bullet lists. "
    "Reference only the numbers given. Do not invent or estimate. "
    "Tone: matter-of-fact, observational. Not motivational. Not preachy."
)

_MONTHLY_USER_TEMPLATE = (
    "Month: {month}\n"
    "Total: {total:.2f}, Count: {count:.0f}, "
    "Avg per active day: {avg_per_day:.2f}, Top category total: {top_category_total:.2f}\n"
    "Breakdown by category: {breakdown}\n"
    "Summarise the spending pattern for this month."
)

_CATEGORY_SYSTEM = (
    "You are a personal finance assistant. Given spending statistics for a single expense category,"
    " write a brief analytical summary.\n"
    "Rules: Write 2-3 short paragraphs of plain prose. No markdown formatting, no bullet lists. "
    "Reference only the numbers given. Do not invent or estimate. "
    "Tone: matter-of-fact, observational. Not motivational. Not preachy."
)

_CATEGORY_USER_TEMPLATE = (
    "Category: {category}\n"
    "Total: {total:.2f}, Count: {count:.0f}, "
    "Avg amount: {avg_amount:.2f}, Max single expense: {max_amount:.2f}\n"
    "Recent descriptions (up to 5): {descriptions}\n"
    "Summarise the spending pattern for this category."
)


def generate_monthly_insight(
    month: str,
    db: Session,
    *,
    llm: LLMClient | None = None,
) -> Insight:
    """Generate a narrative insight for all expenses in a calendar month.

    Args:
        month: Calendar month in YYYY-MM format.
        db:    SQLAlchemy session.
        llm:   Optional pre-constructed LLMClient; a default instance is
               created when None.

    Returns:
        Insight with scope "month:<YYYY-MM>", a narrative, and 4-key stats.

    Raises:
        ValueError:  If *month* is not in YYYY-MM format.
        LLMError:    If the LLM call fails (propagates to caller/endpoint).
    """
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        raise ValueError("month must be in YYYY-MM format")

    year_int, month_int = int(month[:4]), int(month[5:])
    start_date = date(year_int, month_int, 1)
    # First day of next month as the exclusive upper bound
    if month_int == 12:
        end_date_exclusive = date(year_int + 1, 1, 1)
    else:
        end_date_exclusive = date(year_int, month_int + 1, 1)

    stmt = select(Expense).where(
        Expense.occurred_at >= start_date,
        Expense.occurred_at < end_date_exclusive,
    )
    rows: list[Expense] = list(db.execute(stmt).scalars().all())

    total = sum(e.amount for e in rows)
    count = float(len(rows))

    # Per-category totals — used both for stats and prompt context.
    cat_totals: dict[str, float] = defaultdict(float)
    for e in rows:
        cat_totals[e.category] += e.amount

    top_category_total = max(cat_totals.values(), default=0.0)
    active_days = len({e.occurred_at for e in rows})
    avg_per_day = round(total / active_days, 2) if active_days > 0 else 0.0

    stats: dict[str, float] = {
        "total": total,
        "count": count,
        "avg_per_day": avg_per_day,
        "top_category_total": top_category_total,
    }

    # Skip the LLM entirely when there are no expenses — avoids cost for a
    # trivially answerable case and keeps the response instant.
    if count == 0.0:
        return Insight(
            scope=f"month:{month}",
            narrative="No expenses recorded for this month.",
            stats=stats,
        )

    if llm is None:
        llm = LLMClient()

    breakdown_str = ", ".join(f"{cat}: {amt:.2f}" for cat, amt in sorted(cat_totals.items()))
    user_content = _MONTHLY_USER_TEMPLATE.format(
        month=month,
        total=total,
        count=count,
        avg_per_day=avg_per_day,
        top_category_total=top_category_total,
        breakdown=breakdown_str,
    )
    messages: list[dict[str, str]] = [
        {"role": "system", "content": _MONTHLY_SYSTEM},
        {"role": "user", "content": user_content},
    ]
    narrative = llm.chat(messages, json_mode=False, temperature=0.3)
    return Insight(scope=f"month:{month}", narrative=narrative, stats=stats)


def generate_category_insight(
    category: str,
    db: Session,
    *,
    since: date | None = None,
    llm: LLMClient | None = None,
) -> Insight:
    """Generate a narrative insight for a single expense category.

    Args:
        category: Expense category string (free-form, no format restriction).
        db:       SQLAlchemy session.
        since:    Optional lower bound; only expenses on or after this date
                  are included.
        llm:      Optional pre-constructed LLMClient; a default instance is
                  created when None.

    Returns:
        Insight with scope "category:<category>", a narrative, and 4-key stats.

    Raises:
        LLMError: If the LLM call fails (propagates to caller/endpoint).
    """
    stmt = select(Expense).where(Expense.category == category)
    if since is not None:
        stmt = stmt.where(Expense.occurred_at >= since)
    rows: list[Expense] = list(db.execute(stmt).scalars().all())

    total = sum(e.amount for e in rows)
    count = float(len(rows))
    avg_amount = round(total / count, 2) if count > 0 else 0.0
    max_amount = max((e.amount for e in rows), default=0.0)

    stats: dict[str, float] = {
        "total": total,
        "count": count,
        "avg_amount": avg_amount,
        "max_amount": max_amount,
    }

    # Skip the LLM when there are no matching expenses — zero cost for an
    # empty result set.
    if count == 0.0:
        return Insight(
            scope=f"category:{category}",
            narrative=f"No expenses recorded for category '{category}'.",
            stats=stats,
        )

    if llm is None:
        llm = LLMClient()

    # Up to 5 most recent descriptions give the LLM concrete grounding without
    # blowing out the prompt budget.
    recent = sorted(rows, key=lambda e: e.occurred_at, reverse=True)[:5]
    descriptions_str = "; ".join(e.description for e in recent if e.description) or "n/a"

    user_content = _CATEGORY_USER_TEMPLATE.format(
        category=category,
        total=total,
        count=count,
        avg_amount=avg_amount,
        max_amount=max_amount,
        descriptions=descriptions_str,
    )
    messages: list[dict[str, str]] = [
        {"role": "system", "content": _CATEGORY_SYSTEM},
        {"role": "user", "content": user_content},
    ]
    narrative = llm.chat(messages, json_mode=False, temperature=0.3)
    return Insight(scope=f"category:{category}", narrative=narrative, stats=stats)
