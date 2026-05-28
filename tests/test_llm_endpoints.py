from __future__ import annotations

import json
from collections.abc import Generator
from datetime import date
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm import LLMClient, LLMError, get_llm_client
from app.main import app
from app.models import Expense

# ---------------------------------------------------------------------------
# Local fixture — must NOT go into conftest.py
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_llm(client: TestClient) -> Generator[MagicMock, None, None]:  # noqa: ARG001
    """Override get_llm_client dependency with a MagicMock for the duration of
    a single test. The `client` parameter is declared first so that
    conftest's `client` fixture is set up before we add our override and,
    crucially, so that conftest's `app.dependency_overrides.clear()` teardown
    runs AFTER our `pop` — preventing it from wiping the get_db override before
    the client context manager exits.
    """
    mock = MagicMock(spec=LLMClient)
    app.dependency_overrides[get_llm_client] = lambda: mock
    yield mock
    app.dependency_overrides.pop(get_llm_client, None)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_json(
    *,
    amount: float,
    category: str,
    description: str,
    occurred_at: str | None = None,
    confidence: float = 0.9,
) -> str:
    """Return a JSON string in the shape parse_expense_text expects."""
    return json.dumps(
        {
            "amount": amount,
            "category": category,
            "description": description,
            "occurred_at": occurred_at or date.today().isoformat(),
            "confidence": confidence,
        }
    )


# ---------------------------------------------------------------------------
# Test 1: parse endpoint happy path
# ---------------------------------------------------------------------------


def test_parse_endpoint_happy_path(
    client: TestClient,
    mock_llm: MagicMock,
    db_session: Session,
) -> None:
    """POST /expenses/parse returns 200 with parsed fields; no row saved to DB."""
    mock_llm.chat.return_value = _make_json(amount=850.0, category="food", description="lunch")

    response = client.post("/expenses/parse", json={"text": "lunch 850"})

    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "food"
    assert body["amount"] == 850.0
    assert 0.0 <= body["confidence"] <= 1.0

    # Confirm no expense persisted
    rows = db_session.execute(select(Expense)).scalars().all()
    assert len(rows) == 0


# ---------------------------------------------------------------------------
# Test 2: parse endpoint 422 on empty text
# ---------------------------------------------------------------------------


def test_parse_endpoint_422_on_empty_text(
    client: TestClient,
    mock_llm: MagicMock,
) -> None:
    """Empty text violates min_length=1 → 422; LLM is never called."""
    response = client.post("/expenses/parse", json={"text": ""})

    assert response.status_code == 422
    mock_llm.chat.assert_not_called()


# ---------------------------------------------------------------------------
# Test 3: parse endpoint 422 on text too long
# ---------------------------------------------------------------------------


def test_parse_endpoint_422_on_text_too_long(
    client: TestClient,
    mock_llm: MagicMock,
) -> None:
    """Text exceeding max_length=500 → 422; LLM is never called."""
    response = client.post("/expenses/parse", json={"text": "a" * 501})

    assert response.status_code == 422
    mock_llm.chat.assert_not_called()


# ---------------------------------------------------------------------------
# Test 4: parse endpoint 503 on LLMError
# ---------------------------------------------------------------------------


def test_parse_endpoint_503_on_llm_error(
    client: TestClient,
    mock_llm: MagicMock,
) -> None:
    """LLMError from the adapter is surfaced as HTTP 503."""
    mock_llm.chat.side_effect = LLMError("test failure", attempts=["primary"])

    response = client.post("/expenses/parse", json={"text": "groceries 200"})

    assert response.status_code == 503
    assert "LLM unavailable" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Test 5: from-text endpoint creates a DB row
# ---------------------------------------------------------------------------


def test_from_text_endpoint_creates_row(
    client: TestClient,
    mock_llm: MagicMock,
    db_session: Session,
) -> None:
    """POST /expenses/from-text returns 201, body has parsed fields + id, and
    exactly one expense row is written to the DB."""
    today = date.today().isoformat()
    mock_llm.chat.return_value = _make_json(
        amount=180.0,
        category="food",
        description="coffee",
        occurred_at=today,
    )

    response = client.post("/expenses/from-text", json={"text": "coffee 180"})

    assert response.status_code == 201
    body = response.json()
    assert body["amount"] == 180.0
    assert body["category"] == "food"
    assert body["description"] == "coffee"
    assert body["occurred_at"] == today
    assert "id" in body

    rows = db_session.execute(select(Expense)).scalars().all()
    assert len(rows) == 1
    assert rows[0].amount == 180.0


# ---------------------------------------------------------------------------
# Test 6: from-text endpoint 503 → no row written
# ---------------------------------------------------------------------------


def test_from_text_endpoint_503_on_llm_error_does_not_create_row(
    client: TestClient,
    mock_llm: MagicMock,
    db_session: Session,
) -> None:
    """LLMError aborts the request before any DB write; zero rows in DB."""
    mock_llm.chat.side_effect = LLMError("upstream down", attempts=["primary", "fallback"])

    response = client.post("/expenses/from-text", json={"text": "taxi 450"})

    assert response.status_code == 503

    rows = db_session.execute(select(Expense)).scalars().all()
    assert len(rows) == 0


# ---------------------------------------------------------------------------
# Insight endpoint helpers
# ---------------------------------------------------------------------------


_TEST_USER_ID = "00000000-0000-0000-0000-000000000001"  # matches conftest TEST_USER_ID


def _seed_expenses(db: Session, rows: list[dict]) -> None:
    """Insert Expense rows from a list of dicts; commits once at the end.

    Each row is stamped with the test user ID so that the per-user WHERE
    filters added in Phase 3a Step 4 return the seeded data.
    """
    for r in rows:
        row_with_user = {**r, "user_id": _TEST_USER_ID}
        db.add(Expense(**row_with_user))
    db.commit()


# ---------------------------------------------------------------------------
# Test 7: monthly insight — happy path
# ---------------------------------------------------------------------------


def test_monthly_insight_endpoint_happy_path(
    client: TestClient,
    mock_llm: MagicMock,
    db_session: Session,
) -> None:
    """GET /insights/monthly returns 200 with correct scope, narrative, and stats."""
    _seed_expenses(
        db_session,
        [
            {
                "amount": 100.0,
                "category": "food",
                "description": "lunch",
                "occurred_at": date(2026, 5, 1),
            },
            {
                "amount": 200.0,
                "category": "food",
                "description": "dinner",
                "occurred_at": date(2026, 5, 2),
            },
            {
                "amount": 300.0,
                "category": "transport",
                "description": "taxi",
                "occurred_at": date(2026, 5, 3),
            },
        ],
    )
    mock_llm.chat.return_value = "May narrative."

    response = client.get("/insights/monthly?month=2026-05")

    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "month:2026-05"
    assert body["narrative"] == "May narrative."
    assert body["stats"]["count"] == 3.0
    assert body["stats"]["total"] == pytest.approx(600.0)
    assert mock_llm.chat.call_count == 1


# ---------------------------------------------------------------------------
# Test 8: monthly insight — invalid month format → 400
# ---------------------------------------------------------------------------


def test_monthly_insight_endpoint_invalid_month_format(
    client: TestClient,
    mock_llm: MagicMock,
) -> None:
    """Bad month string raises ValueError → 400 with 'YYYY-MM' in detail."""
    response = client.get("/insights/monthly?month=May2026")

    assert response.status_code == 400
    assert "YYYY-MM" in response.json()["detail"]
    assert mock_llm.chat.call_count == 0


# ---------------------------------------------------------------------------
# Test 9: monthly insight — empty DB short-circuits LLM
# ---------------------------------------------------------------------------


def test_monthly_insight_endpoint_no_expenses_short_circuits(
    client: TestClient,
    mock_llm: MagicMock,
) -> None:
    """Empty DB → narrative starts with 'No expenses'; LLM is never called."""
    response = client.get("/insights/monthly?month=2026-05")

    assert response.status_code == 200
    body = response.json()
    assert body["narrative"].startswith("No expenses")
    assert mock_llm.chat.call_count == 0


# ---------------------------------------------------------------------------
# Test 10: monthly insight — LLMError → 503
# ---------------------------------------------------------------------------


def test_monthly_insight_endpoint_503_on_llm_error(
    client: TestClient,
    mock_llm: MagicMock,
    db_session: Session,
) -> None:
    """LLMError from the adapter is surfaced as HTTP 503."""
    _seed_expenses(
        db_session,
        [
            {
                "amount": 50.0,
                "category": "food",
                "description": "snack",
                "occurred_at": date(2026, 5, 10),
            }
        ],
    )
    mock_llm.chat.side_effect = LLMError("test", attempts=["primary"])

    response = client.get("/insights/monthly?month=2026-05")

    assert response.status_code == 503
    assert "LLM unavailable" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Test 11: category insight — happy path
# ---------------------------------------------------------------------------


def test_category_insight_endpoint_happy_path(
    client: TestClient,
    mock_llm: MagicMock,
    db_session: Session,
) -> None:
    """GET /insights/category returns 200 with correct scope and narrative."""
    _seed_expenses(
        db_session,
        [
            {
                "amount": 80.0,
                "category": "food",
                "description": "pizza",
                "occurred_at": date(2026, 5, 1),
            },
            {
                "amount": 120.0,
                "category": "food",
                "description": "sushi",
                "occurred_at": date(2026, 5, 5),
            },
            {
                "amount": 200.0,
                "category": "transport",
                "description": "uber",
                "occurred_at": date(2026, 5, 3),
            },
        ],
    )
    mock_llm.chat.return_value = "Food narrative."

    response = client.get("/insights/category?category=food")

    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "category:food"
    assert body["narrative"] == "Food narrative."
    assert mock_llm.chat.call_count == 1


# ---------------------------------------------------------------------------
# Test 12: category insight — since filter applied
# ---------------------------------------------------------------------------


def test_category_insight_endpoint_with_since_filter(
    client: TestClient,
    mock_llm: MagicMock,
    db_session: Session,
) -> None:
    """?since=2026-05-15 excludes earlier expenses; stats reflect only post-cutoff rows."""
    _seed_expenses(
        db_session,
        [
            {
                "amount": 50.0,
                "category": "food",
                "description": "early lunch",
                "occurred_at": date(2026, 5, 10),
            },
            {
                "amount": 150.0,
                "category": "food",
                "description": "late dinner",
                "occurred_at": date(2026, 5, 20),
            },
            {
                "amount": 250.0,
                "category": "food",
                "description": "weekend brunch",
                "occurred_at": date(2026, 5, 25),
            },
        ],
    )
    mock_llm.chat.return_value = "Filtered food narrative."

    response = client.get("/insights/category?category=food&since=2026-05-15")

    assert response.status_code == 200
    body = response.json()
    # Only the two expenses on/after 2026-05-15 should be counted.
    assert body["stats"]["count"] == 2.0
    assert body["stats"]["total"] == pytest.approx(400.0)
    assert body["narrative"] == "Filtered food narrative."


# ---------------------------------------------------------------------------
# Test 13: category insight — LLMError → 503
# ---------------------------------------------------------------------------


def test_category_insight_endpoint_503_on_llm_error(
    client: TestClient,
    mock_llm: MagicMock,
    db_session: Session,
) -> None:
    """LLMError from the adapter is surfaced as HTTP 503 for category endpoint."""
    _seed_expenses(
        db_session,
        [
            {
                "amount": 75.0,
                "category": "food",
                "description": "burger",
                "occurred_at": date(2026, 5, 5),
            }
        ],
    )
    mock_llm.chat.side_effect = LLMError("upstream error", attempts=["primary"])

    response = client.get("/insights/category?category=food")

    assert response.status_code == 503
    assert "LLM unavailable" in response.json()["detail"]
