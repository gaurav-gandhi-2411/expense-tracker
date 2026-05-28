from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.insights import generate_category_insight, generate_monthly_insight
from app.llm import LLMError
from app.models import Expense
from app.schemas import Insight

TEST_USER_ID = "00000000-0000-0000-0000-000000000001"

# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------


def _seed(
    db: Session,
    amount: float,
    category: str,
    occurred_at: date,
    description: str = "",
    user_id: str = TEST_USER_ID,
) -> Expense:
    """Add a single Expense row and flush (but don't commit) to allow rollback."""
    exp = Expense(
        amount=amount, category=category, description=description,
        occurred_at=occurred_at, user_id=user_id,
    )
    db.add(exp)
    db.commit()
    return exp


# ---------------------------------------------------------------------------
# Monthly insight tests
# ---------------------------------------------------------------------------


def test_monthly_insight_happy_path(db_session: Session) -> None:
    """LLM is called once; returned narrative and stats match seeded data."""
    # Seed 5 expenses in 2026-05 across food and transport
    amounts = [100.0, 200.0, 150.0, 50.0, 300.0]
    categories = ["food", "food", "transport", "food", "transport"]
    days = [1, 5, 10, 15, 20]
    for amt, cat, day in zip(amounts, categories, days, strict=True):
        _seed(db_session, amt, cat, date(2026, 5, day))

    expected_total = sum(amounts)  # 800.0

    mock = MagicMock()
    mock.chat.return_value = "Narrative text here."

    result = generate_monthly_insight("2026-05", db_session, user_id=TEST_USER_ID, llm=mock)

    assert isinstance(result, Insight)
    assert result.scope == "month:2026-05"
    assert result.narrative == "Narrative text here."
    assert result.stats["count"] == 5.0
    assert result.stats["total"] == pytest.approx(expected_total)
    assert set(result.stats.keys()) == {"total", "count", "avg_per_day", "top_category_total"}
    mock.chat.assert_called_once()


def test_monthly_insight_no_expenses_short_circuits(db_session: Session) -> None:
    """Empty DB: LLM must not be called and narrative signals no expenses."""
    mock = MagicMock()

    result = generate_monthly_insight("2026-05", db_session, user_id=TEST_USER_ID, llm=mock)

    assert result.stats["count"] == 0.0
    assert "No expenses recorded" in result.narrative
    assert mock.chat.call_count == 0


def test_monthly_insight_invalid_month_format(db_session: Session) -> None:
    """Single-digit month or wrong format raises ValueError."""
    mock = MagicMock()

    with pytest.raises(ValueError, match="month must be in YYYY-MM format"):
        generate_monthly_insight("2026-5", db_session, user_id=TEST_USER_ID, llm=mock)

    with pytest.raises(ValueError, match="month must be in YYYY-MM format"):
        generate_monthly_insight("May 2026", db_session, user_id=TEST_USER_ID, llm=mock)


def test_monthly_insight_llm_error_propagates(db_session: Session) -> None:
    """LLMError raised by the mock bubbles out without wrapping."""
    _seed(db_session, 500.0, "food", date(2026, 5, 7))

    mock = MagicMock()
    mock.chat.side_effect = LLMError("test", attempts=["primary"])

    with pytest.raises(LLMError):
        generate_monthly_insight("2026-05", db_session, user_id=TEST_USER_ID, llm=mock)


# ---------------------------------------------------------------------------
# Category insight tests
# ---------------------------------------------------------------------------


def test_category_insight_happy_path(db_session: Session) -> None:
    """LLM called once; stats match food-only rows; other categories ignored."""
    # Food expenses
    _seed(db_session, 120.0, "food", date(2026, 5, 1), "Groceries")
    _seed(db_session, 80.0, "food", date(2026, 5, 5), "Lunch")
    _seed(db_session, 60.0, "food", date(2026, 5, 10), "Dinner")
    # Transport — must not appear in food stats
    _seed(db_session, 250.0, "transport", date(2026, 5, 3), "Cab")

    food_total = 120.0 + 80.0 + 60.0  # 260.0

    mock = MagicMock()
    mock.chat.return_value = "Category narrative."

    result = generate_category_insight("food", db_session, user_id=TEST_USER_ID, llm=mock)

    assert isinstance(result, Insight)
    assert result.scope == "category:food"
    assert result.narrative == "Category narrative."
    assert result.stats["total"] == pytest.approx(food_total)
    assert result.stats["count"] == 3.0
    assert set(result.stats.keys()) == {"total", "count", "avg_amount", "max_amount"}
    mock.chat.assert_called_once()


def test_category_insight_no_matches_short_circuits(db_session: Session) -> None:
    """Category with zero rows: LLM not called, narrative signals no expenses."""
    _seed(db_session, 100.0, "food", date(2026, 5, 1))

    mock = MagicMock()

    result = generate_category_insight("shopping", db_session, user_id=TEST_USER_ID, llm=mock)

    assert "No expenses recorded for category" in result.narrative
    assert result.stats["count"] == 0.0
    assert mock.chat.call_count == 0


def test_category_insight_respects_since_filter(db_session: Session) -> None:
    """Only expenses on or after the since date are included in stats."""
    # April expenses — should be excluded
    _seed(db_session, 300.0, "food", date(2026, 4, 20))
    _seed(db_session, 200.0, "food", date(2026, 4, 28))
    # May expenses — should be included
    _seed(db_session, 150.0, "food", date(2026, 5, 3))
    _seed(db_session, 100.0, "food", date(2026, 5, 15))

    mock = MagicMock()
    mock.chat.return_value = "Filtered narrative."

    result = generate_category_insight(
        "food", db_session, user_id=TEST_USER_ID, since=date(2026, 5, 1), llm=mock
    )

    assert result.stats["count"] == 2.0
    assert result.stats["total"] == pytest.approx(250.0)
    assert result.stats["max_amount"] == pytest.approx(150.0)
    mock.chat.assert_called_once()
