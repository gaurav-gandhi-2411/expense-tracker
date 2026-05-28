from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture
from sqlalchemy.orm import Session

from app.ml.anomaly import AnomalyFlag, ExpensePoint
from app.ml.categorizer import CategorySuggestion, TrainResult
from app.ml.forecast import ForecastPoint, ForecastResult
from app.models import Expense

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TODAY = date(2026, 5, 1)


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


# ---------------------------------------------------------------------------
# Test 7 — anomalies: empty DB returns empty list (real function, fast path)
# ---------------------------------------------------------------------------


def test_anomalies_endpoint_returns_empty_list_when_no_expenses(
    client: TestClient,
) -> None:
    """With an empty DB, detect_anomalies returns [] below the sample threshold."""
    response = client.get("/ml/anomalies")

    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# Test 8 — anomalies: mocked detector flags are echoed as response
# ---------------------------------------------------------------------------


def test_anomalies_endpoint_returns_flags_when_detector_finds_some(
    client: TestClient,
    mocker: MockerFixture,
) -> None:
    """When detect_anomalies returns flags, the endpoint serialises them correctly."""
    mocker.patch(
        "app.main.detect_anomalies",
        return_value=[
            AnomalyFlag(
                expense_id=42,
                amount=9999.0,
                category="food",
                reason="50x your typical food spend",
                score=0.95,
            )
        ],
    )

    # Seed one expense so the endpoint has something to pass to detect_anomalies.
    client.post(
        "/expenses",
        json={
            "amount": 20.0,
            "category": "food",
            "description": "lunch",
            "occurred_at": "2025-06-01",
        },
    )

    response = client.get("/ml/anomalies")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["expense_id"] == 42
    assert body[0]["reason"] == "50x your typical food spend"
    assert body[0]["score"] == pytest.approx(0.95)


# ---------------------------------------------------------------------------
# Test 9 — anomalies: since= param filters expenses before detection
# ---------------------------------------------------------------------------


def test_anomalies_endpoint_filters_by_since_param(
    client: TestClient,
    mocker: MockerFixture,
) -> None:
    """Only expenses on/after `since` are passed to detect_anomalies."""
    captured: list[list[ExpensePoint]] = []

    def _capturing_detect(expenses):  # type: ignore[no-untyped-def]
        captured.append(expenses)
        return []

    mocker.patch("app.main.detect_anomalies", side_effect=_capturing_detect)

    # Seed two expenses with different dates.
    client.post(
        "/expenses",
        json={
            "amount": 10.0,
            "category": "food",
            "description": "old",
            "occurred_at": "2024-01-01",
        },
    )
    client.post(
        "/expenses",
        json={
            "amount": 20.0,
            "category": "food",
            "description": "new",
            "occurred_at": "2025-12-01",
        },
    )

    response = client.get("/ml/anomalies?since=2025-01-01")

    assert response.status_code == 200
    assert len(captured) == 1
    points = captured[0]
    assert len(points) == 1
    assert str(points[0].occurred_at) == "2025-12-01"


# ---------------------------------------------------------------------------
# Test 10 — anomalies: ORM→ExpensePoint mapping is correct
# ---------------------------------------------------------------------------


def test_anomalies_endpoint_passes_expense_points_with_expected_fields(
    client: TestClient,
    mocker: MockerFixture,
) -> None:
    """The ExpensePoint passed to detect_anomalies mirrors the seeded expense exactly."""
    captured: list[list] = []

    def _capturing_detect(expenses):  # type: ignore[no-untyped-def]
        captured.append(expenses)
        return []

    mocker.patch("app.main.detect_anomalies", side_effect=_capturing_detect)

    resp = client.post(
        "/expenses",
        json={
            "amount": 75.5,
            "category": "transport",
            "description": "taxi",
            "occurred_at": "2025-03-15",
        },
    )
    assert resp.status_code == 201
    seeded_id = resp.json()["id"]

    response = client.get("/ml/anomalies")

    assert response.status_code == 200
    assert len(captured) == 1
    points = captured[0]
    assert len(points) == 1
    p = points[0]
    assert p.id == seeded_id
    assert p.amount == pytest.approx(75.5)
    assert p.category == "transport"
    assert str(p.occurred_at) == "2025-03-15"


# ---------------------------------------------------------------------------
# Test 11 — forecast: prophet result is serialised correctly
# ---------------------------------------------------------------------------


def test_forecast_endpoint_returns_prophet_result_when_mocked(
    client: TestClient,
    mocker: MockerFixture,
) -> None:
    """GET /ml/forecast returns 200 and echoes the ForecastResult fields correctly."""
    mocker.patch(
        "app.main.forecast_spend",
        return_value=ForecastResult(
            horizon_months=2,
            points=[
                ForecastPoint(month="2025-07", predicted=1500.0, lower=1300.0, upper=1700.0),
                ForecastPoint(month="2025-08", predicted=1600.0, lower=1400.0, upper=1800.0),
            ],
            mode="prophet",
            note="ok",
        ),
    )

    response = client.get("/ml/forecast?horizon=2")

    assert response.status_code == 200
    body = response.json()
    assert body["horizon_months"] == 2
    assert body["mode"] == "prophet"
    assert len(body["points"]) == 2
    assert body["points"][0]["month"] == "2025-07"
    assert body["points"][0]["predicted"] == pytest.approx(1500.0)


# ---------------------------------------------------------------------------
# Test 12 — forecast: default horizon_months is 1
# ---------------------------------------------------------------------------


def test_forecast_endpoint_default_horizon_is_1(
    client: TestClient,
    mocker: MockerFixture,
) -> None:
    """Calling GET /ml/forecast without ?horizon passes horizon_months=1 to forecast_spend."""
    captured_kwargs: list[dict] = []

    def _capturing_forecast(series, horizon_months=1):  # type: ignore[no-untyped-def]
        captured_kwargs.append({"horizon_months": horizon_months})
        return ForecastResult(
            horizon_months=horizon_months,
            points=[],
            mode="low-confidence-average",
            note="No historical data; forecast unavailable.",
        )

    mocker.patch("app.main.forecast_spend", side_effect=_capturing_forecast)

    response = client.get("/ml/forecast")

    assert response.status_code == 200
    assert len(captured_kwargs) == 1
    assert captured_kwargs[0]["horizon_months"] == 1


# ---------------------------------------------------------------------------
# Test 13 — forecast: low-confidence-average mode is serialised correctly
# ---------------------------------------------------------------------------


def test_forecast_endpoint_returns_low_confidence_result_when_mocked(
    client: TestClient,
    mocker: MockerFixture,
) -> None:
    """The endpoint correctly serialises a low-confidence-average ForecastResult."""
    mocker.patch(
        "app.main.forecast_spend",
        return_value=ForecastResult(
            horizon_months=3,
            points=[
                ForecastPoint(month="2025-09", predicted=800.0, lower=400.0, upper=1200.0),
                ForecastPoint(month="2025-10", predicted=800.0, lower=400.0, upper=1200.0),
                ForecastPoint(month="2025-11", predicted=800.0, lower=400.0, upper=1200.0),
            ],
            mode="low-confidence-average",
            note="Only 2 months of history; using simple average as a low-confidence projection.",
        ),
    )

    response = client.get("/ml/forecast?horizon=3")

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "low-confidence-average"
    assert body["note"] != ""


# ---------------------------------------------------------------------------
# Test 14 — forecast: invalid horizon raises 400
# ---------------------------------------------------------------------------


def test_forecast_endpoint_invalid_horizon_returns_400(
    client: TestClient,
    mocker: MockerFixture,
) -> None:
    """When forecast_spend raises ValueError for horizon < 1, the endpoint returns HTTP 400."""
    mocker.patch(
        "app.main.forecast_spend",
        side_effect=ValueError("horizon_months must be >= 1, got 0"),
    )

    response = client.get("/ml/forecast?horizon=0")

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "horizon_months" in detail or ">= 1" in detail


# ---------------------------------------------------------------------------
# Test 15 — forecast: monthly series from DB is forwarded to forecast_spend
# ---------------------------------------------------------------------------


def test_forecast_endpoint_passes_monthly_series_from_db(
    client: TestClient,
    mocker: MockerFixture,
) -> None:
    """The (month, total) series built from DB aggregation reaches forecast_spend."""
    captured_series: list[list[tuple[str, float]]] = []

    def _capturing_forecast(series, horizon_months=1):  # type: ignore[no-untyped-def]
        captured_series.append(series)
        return ForecastResult(
            horizon_months=horizon_months,
            points=[],
            mode="low-confidence-average",
            note="No historical data; forecast unavailable.",
        )

    mocker.patch("app.main.forecast_spend", side_effect=_capturing_forecast)

    # Seed two expenses in different months so total_by_month returns at least 2 rows.
    client.post(
        "/expenses",
        json={
            "amount": 100.0,
            "category": "food",
            "description": "lunch",
            "occurred_at": "2025-03-15",
        },
    )
    client.post(
        "/expenses",
        json={
            "amount": 200.0,
            "category": "transport",
            "description": "taxi",
            "occurred_at": "2025-04-10",
        },
    )

    response = client.get("/ml/forecast?horizon=1")

    assert response.status_code == 200
    assert len(captured_series) == 1
    series = captured_series[0]

    # The series must be a list of (month_str, total) tuples.
    assert isinstance(series, list)
    months_in_series = [month for month, _ in series]
    assert "2025-03" in months_in_series
    assert "2025-04" in months_in_series
