from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture
from sqlalchemy.orm import Session

from app.ml.categorizer import CategorySuggestion, TrainResult
from app.models import Expense

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TODAY = date(2026, 5, 1)


def _seed_expenses(db: Session, rows: list[dict]) -> None:
    """Insert Expense rows from a list of dicts; commits once at the end."""
    for r in rows:
        db.add(Expense(**r))
    db.commit()


# ---------------------------------------------------------------------------
# Test 1 — categorize: happy path with mocked categorizer
# ---------------------------------------------------------------------------


def test_categorize_endpoint_returns_suggestion_with_mocked_categorizer(
    client: TestClient,
    mocker: MockerFixture,
) -> None:
    """POST /ml/categorize returns 200 with the suggestion from suggest_category."""
    mock_suggest = mocker.patch(
        "app.main.suggest_category",
        return_value=CategorySuggestion(category="transport", score=0.87, mode="zero-shot"),
    )

    response = client.post("/ml/categorize", json={"text": "uber to airport"})

    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "transport"
    assert body["score"] == pytest.approx(0.87)
    assert body["mode"] == "zero-shot"

    # The patched function should have been called exactly once.
    mock_suggest.assert_called_once()
    call_args = mock_suggest.call_args
    assert call_args[0][0] == "uber to airport"  # first positional arg: text


# ---------------------------------------------------------------------------
# Test 2 — categorize: DB categories are merged with defaults
# ---------------------------------------------------------------------------


def test_categorize_endpoint_merges_db_categories_with_defaults(
    client: TestClient,
    mocker: MockerFixture,
    db_session: Session,
) -> None:
    """Prototypes passed to suggest_category include both DB-specific and default categories."""
    # Seed one expense whose category does NOT appear in DEFAULT_PROTOTYPES.
    _seed_expenses(
        db_session,
        [
            {
                "amount": 500.0,
                "category": "travel",
                "description": "flight ticket",
                "occurred_at": _TODAY,
            }
        ],
    )

    captured: list[list[str]] = []

    def _capturing_suggest(text: str, prototypes: list[str]) -> CategorySuggestion:
        captured.append(prototypes)
        return CategorySuggestion(category="travel", score=0.91, mode="zero-shot")

    mocker.patch("app.main.suggest_category", side_effect=_capturing_suggest)

    response = client.post("/ml/categorize", json={"text": "flight to Tokyo"})

    assert response.status_code == 200
    assert len(captured) == 1
    prototypes = captured[0]

    # Custom DB category must be present.
    assert "travel" in prototypes
    # At least one default category must also be present.
    assert "food" in prototypes
    # The list must be sorted (endpoint uses sorted()).
    assert prototypes == sorted(prototypes)


# ---------------------------------------------------------------------------
# Test 3 — categorize: empty text fails validation (422)
# ---------------------------------------------------------------------------


def test_categorize_endpoint_validates_empty_text(
    client: TestClient,
) -> None:
    """Empty text violates TextInput.min_length=1 and must return 422."""
    response = client.post("/ml/categorize", json={"text": ""})

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Test 4 — train-categorizer: refuses on empty DB (real function, no mock)
# ---------------------------------------------------------------------------


def test_train_categorizer_endpoint_refuses_on_empty_db(
    client: TestClient,
) -> None:
    """With no DB rows, the real train_categorizer returns refused-insufficient-data instantly."""
    # No patching — exercise the real refusal guard on an empty labeled list.
    response = client.post("/ml/train-categorizer")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "refused-insufficient-data"
    assert body["metrics"] is None
    assert body["n_examples"] == 0


# ---------------------------------------------------------------------------
# Test 5 — train-categorizer: labeled data passed matches seeded expenses
# ---------------------------------------------------------------------------


def test_train_categorizer_endpoint_passes_labeled_data_from_db(
    client: TestClient,
    mocker: MockerFixture,
    db_session: Session,
) -> None:
    """The (description, category) tuples forwarded to train_categorizer match the DB rows.

    Rows with empty descriptions must be filtered out before the call.
    """
    seeded = [
        {"amount": 100.0, "category": "food", "description": "lunch", "occurred_at": _TODAY},
        {"amount": 200.0, "category": "transport", "description": "taxi", "occurred_at": _TODAY},
        {"amount": 50.0, "category": "food", "description": "coffee", "occurred_at": _TODAY},
        # Empty description — must be excluded from labeled data.
        {"amount": 300.0, "category": "rent", "description": "", "occurred_at": _TODAY},
    ]
    _seed_expenses(db_session, seeded)

    captured_labeled: list[list[tuple[str, str]]] = []
    refusal = TrainResult(
        status="refused-insufficient-data",
        reason="mocked refusal",
        n_examples=0,
        n_categories=0,
        metrics=None,
    )

    def _capturing_train(labeled: list[tuple[str, str]]) -> TrainResult:
        captured_labeled.append(labeled)
        return refusal

    mocker.patch("app.main.train_categorizer", side_effect=_capturing_train)

    response = client.post("/ml/train-categorizer")

    assert response.status_code == 200
    assert response.json()["status"] == "refused-insufficient-data"

    assert len(captured_labeled) == 1
    labeled = captured_labeled[0]

    # The empty-description row must have been filtered out.
    assert all(desc.strip() for desc, _ in labeled)

    # The three non-empty rows must appear (order may vary depending on DB).
    expected = {("lunch", "food"), ("taxi", "transport"), ("coffee", "food")}
    assert set(labeled) == expected


# ---------------------------------------------------------------------------
# Test 6 — train-categorizer: returns trained status when mock says so
# ---------------------------------------------------------------------------


def test_train_categorizer_endpoint_returns_trained_status_when_mock_says_so(
    client: TestClient,
    mocker: MockerFixture,
) -> None:
    """When train_categorizer returns a trained TrainResult, the endpoint echoes it."""
    trained_result = TrainResult(
        status="trained",
        reason="trained on 60 examples across 2 categories",
        n_examples=60,
        n_categories=2,
        metrics={"accuracy": 1.0},
    )
    mocker.patch("app.main.train_categorizer", return_value=trained_result)

    response = client.post("/ml/train-categorizer")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "trained"
    assert body["n_examples"] == 60
    assert body["n_categories"] == 2
    assert body["metrics"] is not None
    assert body["metrics"]["accuracy"] == pytest.approx(1.0)
