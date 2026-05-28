from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Expense
from app.schemas import ParsedExpense

TEST_USER_A = "00000000-0000-0000-0000-000000000001"  # matches conftest TEST_USER_ID
TEST_USER_B = "00000000-0000-0000-0000-000000000002"


def _make_b_expense(db_session: Session, **kwargs: object) -> Expense:
    """Insert a user B expense directly, bypassing the endpoint."""
    defaults: dict[str, object] = dict(
        amount=500.0,
        category="food",
        description="user B expense",
        occurred_at=date(2026, 1, 15),
        user_id=TEST_USER_B,
    )
    defaults.update(kwargs)
    row = Expense(**defaults)  # type: ignore[arg-type]
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


# ---------------------------------------------------------------------------
# GET /health — public, no isolation concern
# ---------------------------------------------------------------------------


def test_health_is_public(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /expenses — stamps the authenticated user's id
# ---------------------------------------------------------------------------


def test_create_expense_assigns_own_user_id(client: TestClient, db_session: Session) -> None:
    resp = client.post(
        "/expenses",
        json={"amount": 100.0, "category": "food", "description": "", "occurred_at": "2026-01-01"},
    )
    assert resp.status_code == 201
    row = db_session.get(Expense, resp.json()["id"])
    assert row is not None
    assert row.user_id == TEST_USER_A


# ---------------------------------------------------------------------------
# GET /expenses — list excludes other user's data
# ---------------------------------------------------------------------------


def test_list_expenses_excludes_other_user(client: TestClient, db_session: Session) -> None:
    b = _make_b_expense(db_session)
    resp = client.get("/expenses")
    assert resp.status_code == 200
    ids = [e["id"] for e in resp.json()]
    assert b.id not in ids


# ---------------------------------------------------------------------------
# GET /expenses/{id} — 404 on cross-user access
# ---------------------------------------------------------------------------


def test_get_expense_cross_user_returns_404(client: TestClient, db_session: Session) -> None:
    b = _make_b_expense(db_session)
    resp = client.get(f"/expenses/{b.id}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /expenses/{id} — 404 on cross-user access
# ---------------------------------------------------------------------------


def test_patch_expense_cross_user_returns_404(client: TestClient, db_session: Session) -> None:
    b = _make_b_expense(db_session)
    resp = client.patch(f"/expenses/{b.id}", json={"amount": 1.0})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /expenses/{id} — 404 on cross-user access
# ---------------------------------------------------------------------------


def test_delete_expense_cross_user_returns_404(client: TestClient, db_session: Session) -> None:
    b = _make_b_expense(db_session)
    resp = client.delete(f"/expenses/{b.id}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /stats/by-month — excludes other user's data
# ---------------------------------------------------------------------------


def test_stats_by_month_excludes_other_user(client: TestClient, db_session: Session) -> None:
    _make_b_expense(db_session, amount=9999.0, occurred_at=date(2026, 1, 1))
    resp = client.get("/stats/by-month")
    assert resp.status_code == 200
    assert resp.json() == []  # user A has no expenses


# ---------------------------------------------------------------------------
# GET /stats/by-category — excludes other user's data
# ---------------------------------------------------------------------------


def test_stats_by_category_excludes_other_user(client: TestClient, db_session: Session) -> None:
    _make_b_expense(db_session, category="secret_category", amount=9999.0)
    resp = client.get("/stats/by-category")
    assert resp.status_code == 200
    categories = [r["category"] for r in resp.json()]
    assert "secret_category" not in categories


# ---------------------------------------------------------------------------
# POST /expenses/parse — no DB read; just verifies auth is enforced
# ---------------------------------------------------------------------------


def test_parse_expense_requires_no_db_access(client: TestClient) -> None:
    # parse endpoint doesn't read DB; auth is already verified by test_auth.py.
    # Here we just confirm the endpoint is reachable with a valid (overridden) auth.
    resp = client.post("/expenses/parse", json={"text": "lunch 100"})
    # 200 or 503 (LLM unavailable in test env) — both mean auth passed
    assert resp.status_code in (200, 503)


# ---------------------------------------------------------------------------
# POST /expenses/from-text — stamps the authenticated user's id
# ---------------------------------------------------------------------------


def test_from_text_assigns_own_user_id(
    client: TestClient, db_session: Session, mocker: pytest.MonkeyPatch
) -> None:
    mocker.patch(
        "app.main.parse_expense_text",
        return_value=ParsedExpense(
            amount=100.0,
            category="food",
            description="test lunch",
            occurred_at=date(2026, 1, 1),
            confidence=0.9,
        ),
    )
    resp = client.post("/expenses/from-text", json={"text": "lunch 100"})
    assert resp.status_code == 201
    row = db_session.get(Expense, resp.json()["id"])
    assert row is not None
    assert row.user_id == TEST_USER_A


# ---------------------------------------------------------------------------
# GET /insights/monthly — user B's expenses don't bleed into user A's insight
# (the empty-DB short-circuit fires for user A → no LLM call needed)
# ---------------------------------------------------------------------------


def test_monthly_insight_excludes_other_user(client: TestClient, db_session: Session) -> None:
    _make_b_expense(db_session, amount=9999.0, occurred_at=date(2026, 1, 15))
    resp = client.get("/insights/monthly?month=2026-01")
    assert resp.status_code == 200
    # User A has 0 expenses for Jan 2026, so the short-circuit path fires
    assert resp.json()["stats"]["count"] == 0.0
    assert "No expenses recorded" in resp.json()["narrative"]


# ---------------------------------------------------------------------------
# GET /insights/category — user B's data doesn't bleed into user A's insight
# ---------------------------------------------------------------------------


def test_category_insight_excludes_other_user(client: TestClient, db_session: Session) -> None:
    _make_b_expense(db_session, category="food", amount=9999.0)
    resp = client.get("/insights/category?category=food")
    assert resp.status_code == 200
    assert resp.json()["stats"]["count"] == 0.0
    assert "No expenses recorded" in resp.json()["narrative"]


# ---------------------------------------------------------------------------
# POST /ml/categorize — user B's categories are not included in the prototype pool
# ---------------------------------------------------------------------------


def test_categorize_excludes_other_user_categories(client: TestClient, db_session: Session) -> None:
    _make_b_expense(db_session, category="user_b_secret_category")
    resp = client.post("/ml/categorize", json={"text": "random text"})
    assert resp.status_code == 200
    # user_b_secret_category should NOT appear in the suggestion pool
    # (it only would if user B's categories were included in the distinct query)
    assert resp.json()["category"] != "user_b_secret_category"


# ---------------------------------------------------------------------------
# POST /ml/train-categorizer — uses only user A's data; refuses when user A
# has no data (proving user B's data isn't included)
# ---------------------------------------------------------------------------


def test_train_categorizer_uses_only_own_data(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app import config

    monkeypatch.setenv("ADMIN_ENABLED", "true")
    config.get_settings.cache_clear()
    _make_b_expense(db_session)  # user B has data; user A has none
    resp = client.post("/ml/train-categorizer")
    assert resp.status_code == 200
    assert resp.json()["status"] == "refused-insufficient-data"
    config.get_settings.cache_clear()


# ---------------------------------------------------------------------------
# GET /ml/anomalies — user B's expenses (60 rows) don't bleed into user A's
# anomaly detection; user A has 0 rows (below threshold → empty list)
# ---------------------------------------------------------------------------


def test_anomalies_excludes_other_user(client: TestClient, db_session: Session) -> None:
    for i in range(60):
        _make_b_expense(db_session, amount=float((i + 1) * 100))
    resp = client.get("/ml/anomalies")
    assert resp.status_code == 200
    assert resp.json() == []  # user A has 0 expenses, below threshold


# ---------------------------------------------------------------------------
# GET /ml/forecast — user B's monthly totals don't appear in user A's forecast
# ---------------------------------------------------------------------------


def test_forecast_excludes_other_user(client: TestClient, db_session: Session) -> None:
    _make_b_expense(db_session, amount=9999.0, occurred_at=date(2026, 1, 15))
    resp = client.get("/ml/forecast?horizon=1")
    assert resp.status_code == 200
    data = resp.json()
    # User A has 0 expenses → low-confidence-average with no points
    assert data["mode"] == "low-confidence-average"
    assert data["points"] == []
