"""Tests for app.ml.forecast — Prophet is fully mocked; no real model is ever fitted.

Patching strategy: ``app.ml.forecast._get_prophet`` is patched (not
``app.ml.forecast.Prophet``) because the module uses a deferred-import helper
to avoid adding ~1.5 s of Prophet import overhead to pytest collection time.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from app.ml.forecast import forecast_spend

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_prophet_mock(mocker: MagicMock, predict_df: pd.DataFrame) -> MagicMock:
    """Return a patched ``_get_prophet`` whose instance replays *predict_df*.

    The returned mock makes ``_get_prophet()`` return a class mock whose
    ``__call__`` produces an instance that:
      - ``fit`` returns itself (fluent)
      - ``make_future_dataframe`` returns *predict_df* (content irrelevant; predict is
        the authoritative source)
      - ``predict`` returns *predict_df*

    Tests that need to inspect ``fit``'s argument can access
    ``mock_instance.fit.call_args``.
    """
    mock_instance = MagicMock()
    mock_instance.fit.return_value = mock_instance
    mock_instance.make_future_dataframe.return_value = predict_df
    mock_instance.predict.return_value = predict_df

    mock_class = MagicMock(return_value=mock_instance)

    mocker.patch("app.ml.forecast._get_prophet", return_value=mock_class)
    return mock_instance


def _synthetic_forecast_df(months: list[str], base: float = 1000.0) -> pd.DataFrame:
    """Build a minimal forecast DataFrame with the columns Prophet produces.

    Args:
        months: List of ``"YYYY-MM"`` strings for the ``ds`` column.
        base:   Base value for ``yhat``; ``yhat_lower`` = base*0.9, ``yhat_upper`` = base*1.1.

    Returns:
        DataFrame with columns ``ds``, ``yhat``, ``yhat_lower``, ``yhat_upper``.
    """
    return pd.DataFrame(
        {
            "ds": pd.to_datetime([f"{m}-01" for m in months]),
            "yhat": [base + i * 10 for i in range(len(months))],
            "yhat_lower": [(base + i * 10) * 0.9 for i in range(len(months))],
            "yhat_upper": [(base + i * 10) * 1.1 for i in range(len(months))],
        }
    )


# ---------------------------------------------------------------------------
# 1. Empty input
# ---------------------------------------------------------------------------


class TestForecastEmptyInput:
    def test_forecast_empty_input_returns_low_confidence_with_no_points(self) -> None:
        """Empty monthly_totals must return low-confidence with points=[]."""
        result = forecast_spend([], horizon_months=3)

        assert result.mode == "low-confidence-average"
        assert result.points == []
        assert result.horizon_months == 3
        assert len(result.note) > 0


# ---------------------------------------------------------------------------
# 2. Below threshold (low-confidence average)
# ---------------------------------------------------------------------------


class TestForecastBelowThreshold:
    def test_forecast_below_threshold_returns_low_confidence_average(self) -> None:
        """Two months of data (below default 3) → simple-average projection."""
        monthly = [("2025-01", 1000.0), ("2025-02", 1200.0)]
        result = forecast_spend(monthly, horizon_months=2)

        assert result.mode == "low-confidence-average"
        assert len(result.points) == 2

        expected_avg = 1100.0  # (1000 + 1200) / 2
        for point in result.points:
            assert point.predicted == pytest.approx(expected_avg)
            assert point.lower < point.predicted
            assert point.predicted < point.upper

        months = [p.month for p in result.points]
        assert months == ["2025-03", "2025-04"]

        # Note must mention the low-confidence or simple-average situation.
        note_lower = result.note.lower()
        assert "low-confidence" in note_lower or "simple average" in note_lower

    def test_forecast_horizon_respected_in_low_confidence_path(self) -> None:
        """Below-threshold input with horizon=5 produces exactly 5 ForecastPoints."""
        monthly = [("2025-01", 500.0), ("2025-02", 600.0)]
        result = forecast_spend(monthly, horizon_months=5)

        assert result.mode == "low-confidence-average"
        assert len(result.points) == 5


# ---------------------------------------------------------------------------
# 3. Invalid horizon
# ---------------------------------------------------------------------------


class TestForecastInvalidHorizon:
    def test_forecast_invalid_horizon_raises_value_error(self) -> None:
        """horizon_months=0 must raise ValueError."""
        with pytest.raises(ValueError):
            forecast_spend([], horizon_months=0)

    def test_forecast_negative_horizon_raises_value_error(self) -> None:
        """horizon_months=-1 must also raise ValueError."""
        with pytest.raises(ValueError):
            forecast_spend([], horizon_months=-1)


# ---------------------------------------------------------------------------
# 4. Above threshold — Prophet called
# ---------------------------------------------------------------------------


class TestForecastAboveThreshold:
    def test_forecast_above_threshold_calls_prophet(self, mocker: MagicMock) -> None:
        """6 months of data → mode='prophet'; points match the mocked predict output."""
        monthly = [(f"2025-{m:02d}", 1000.0 + m * 50) for m in range(1, 7)]
        future_months = ["2025-07", "2025-08"]
        predict_df = _synthetic_forecast_df(future_months, base=1400.0)

        _make_prophet_mock(mocker, predict_df)

        result = forecast_spend(monthly, horizon_months=2)

        assert result.mode == "prophet"
        assert len(result.points) == 2

        assert result.points[0].month == "2025-07"
        assert result.points[1].month == "2025-08"

        assert result.points[0].predicted == pytest.approx(1400.0)
        assert result.points[0].lower == pytest.approx(1400.0 * 0.9)
        assert result.points[0].upper == pytest.approx(1400.0 * 1.1)

        assert result.points[1].predicted == pytest.approx(1410.0)
        assert result.points[1].lower == pytest.approx(1410.0 * 0.9)
        assert result.points[1].upper == pytest.approx(1410.0 * 1.1)

    def test_forecast_prophet_called_with_correct_dataframe_shape(
        self, mocker: MagicMock
    ) -> None:
        """Prophet's fit() receives a DataFrame with columns [ds, y] and 6 rows."""
        monthly = [(f"2025-{m:02d}", 1000.0 + m * 50) for m in range(1, 7)]
        future_months = ["2025-07", "2025-08"]
        predict_df = _synthetic_forecast_df(future_months, base=1400.0)

        mock_instance = _make_prophet_mock(mocker, predict_df)

        forecast_spend(monthly, horizon_months=2)

        # Inspect the DataFrame passed to fit().
        call_args = mock_instance.fit.call_args
        assert call_args is not None, "Prophet.fit was not called"
        fit_df: pd.DataFrame = call_args[0][0]

        assert list(fit_df.columns) == ["ds", "y"]
        assert len(fit_df) == 6

        # ds values should be datetime-like (month-start)
        assert pd.api.types.is_datetime64_any_dtype(fit_df["ds"])

        # y values must match the input totals in order
        expected_y = [1000.0 + m * 50 for m in range(1, 7)]
        assert list(fit_df["y"]) == pytest.approx(expected_y)

    def test_forecast_result_note_mentions_history_length(
        self, mocker: MagicMock
    ) -> None:
        """Prophet result note must mention the number of history months."""
        monthly = [(f"2025-{m:02d}", 1000.0 + m * 50) for m in range(1, 7)]
        future_months = ["2025-07"]
        predict_df = _synthetic_forecast_df(future_months, base=1400.0)

        _make_prophet_mock(mocker, predict_df)

        result = forecast_spend(monthly, horizon_months=1)

        assert "6" in result.note
        assert result.mode == "prophet"


# ---------------------------------------------------------------------------
# 5. Return-type / structure contract
# ---------------------------------------------------------------------------


class TestForecastReturnType:
    def test_forecast_result_is_frozen_dataclass(self) -> None:
        """ForecastResult must be immutable (frozen=True)."""
        result = forecast_spend([], horizon_months=1)
        with pytest.raises((AttributeError, TypeError)):
            result.mode = "mutated"  # type: ignore[misc]

    def test_forecast_result_horizon_always_matches_input(self) -> None:
        """ForecastResult.horizon_months always equals the caller's argument."""
        for h in [1, 3, 12]:
            result = forecast_spend([], horizon_months=h)
            assert result.horizon_months == h

    def test_low_confidence_lower_and_upper_bracket_predicted(self) -> None:
        """For every low-confidence point, lower < predicted < upper."""
        monthly = [("2024-11", 800.0), ("2024-12", 900.0)]
        result = forecast_spend(monthly, horizon_months=3)

        assert result.mode == "low-confidence-average"
        for point in result.points:
            assert point.lower < point.predicted
            assert point.predicted < point.upper

    def test_low_confidence_month_labels_are_sequential(self) -> None:
        """Month labels in the low-confidence path must be strictly ascending."""
        monthly = [("2025-11", 700.0), ("2025-12", 800.0)]
        result = forecast_spend(monthly, horizon_months=3)

        months = [p.month for p in result.points]
        assert months == ["2026-01", "2026-02", "2026-03"]
