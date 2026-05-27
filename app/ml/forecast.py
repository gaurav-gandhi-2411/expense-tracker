"""Prophet-based monthly spend forecaster with a low-confidence fallback for thin data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

from app.config import get_settings

# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ForecastPoint:
    """A single month's forecast output."""

    month: str        # "YYYY-MM"
    predicted: float
    lower: float
    upper: float


@dataclass(frozen=True)
class ForecastResult:
    """Container returned by :func:`forecast_spend`."""

    horizon_months: int
    points: list[ForecastPoint]
    mode: str         # "prophet" | "low-confidence-average"
    note: str         # human-readable explanation; always non-empty


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_prophet() -> Any:
    """Deferred import of Prophet to avoid ~1.5 s module-level import at collection time.

    Importing at the top level would add ~1.5 s to pytest collection time (above the
    2 s threshold mentioned in the spec), so we defer to first call instead.
    Tests patch this function directly: ``mocker.patch("app.ml.forecast._get_prophet")``.
    """
    from prophet import Prophet  # type: ignore[import-untyped]  # noqa: PLC0415

    return Prophet


def _next_month_label(year: int, month: int) -> tuple[int, int]:
    """Return ``(year, month)`` for the month following the given one."""
    if month == 12:
        return year + 1, 1
    return year, month + 1


def _generate_future_months(last_label: str, n: int) -> list[str]:
    """Return *n* consecutive ``"YYYY-MM"`` strings starting one month after *last_label*.

    Args:
        last_label: The most recent input month in ``"YYYY-MM"`` format.
        n:          Number of future labels to produce.

    Returns:
        List of ``n`` month strings in ascending chronological order.
    """
    year, month = int(last_label[:4]), int(last_label[5:7])
    labels: list[str] = []
    for _ in range(n):
        year, month = _next_month_label(year, month)
        labels.append(f"{year}-{month:02d}")
    return labels


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def forecast_spend(
    monthly_totals: list[tuple[str, float]],
    horizon_months: int = 1,
) -> ForecastResult:
    """Forecast future monthly spend from a pre-aggregated monthly series.

    When history is below ``min_forecast_months`` (default 3) or empty, returns a
    low-confidence simple-average projection instead of calling Prophet — this avoids
    overfitting on thin data and prevents crashes on empty input.

    Args:
        monthly_totals: Pre-aggregated series as ``[("YYYY-MM", total), ...]`` sorted
                        ascending by month.  The caller (Step 5b endpoint) is responsible
                        for aggregating raw DB rows before passing in.
        horizon_months: Number of future months to forecast.  Must be >= 1.

    Returns:
        :class:`ForecastResult` with ``mode`` set to ``"prophet"`` when Prophet was used
        or ``"low-confidence-average"`` when the fallback was applied.

    Raises:
        ValueError: When *horizon_months* is less than 1.
    """
    if horizon_months < 1:
        raise ValueError(f"horizon_months must be >= 1, got {horizon_months}")

    threshold = get_settings().min_forecast_months

    # ------------------------------------------------------------------
    # Low-confidence path — empty input
    # ------------------------------------------------------------------
    if len(monthly_totals) == 0:
        return ForecastResult(
            horizon_months=horizon_months,
            points=[],
            mode="low-confidence-average",
            note="No historical data; forecast unavailable.",
        )

    # ------------------------------------------------------------------
    # Low-confidence path — below threshold
    # ------------------------------------------------------------------
    if len(monthly_totals) < threshold:
        totals = [t for _, t in monthly_totals]
        avg = sum(totals) / len(totals)
        last_label = monthly_totals[-1][0]
        future_labels = _generate_future_months(last_label, horizon_months)
        points = [
            ForecastPoint(
                month=label,
                predicted=avg,
                lower=avg * 0.5,
                upper=avg * 1.5,
            )
            for label in future_labels
        ]
        return ForecastResult(
            horizon_months=horizon_months,
            points=points,
            mode="low-confidence-average",
            note=(
                f"Only {len(monthly_totals)} months of history; "
                "using simple average as a low-confidence projection."
            ),
        )

    # ------------------------------------------------------------------
    # Prophet path
    # ------------------------------------------------------------------
    df = pd.DataFrame(
        {
            "ds": pd.to_datetime([f"{label}-01" for label, _ in monthly_totals]),
            "y": [t for _, t in monthly_totals],
        }
    )

    ProphetClass = _get_prophet()
    model = ProphetClass(
        weekly_seasonality=False,
        daily_seasonality=False,
        seasonality_mode="additive",
        yearly_seasonality="auto",
    )
    model.fit(df)

    future = model.make_future_dataframe(periods=horizon_months, freq="MS")
    forecast = model.predict(future)

    # Take only the last horizon_months rows — the tail of the forecast DataFrame.
    tail = forecast.tail(horizon_months)

    points = [
        ForecastPoint(
            month=row.ds.strftime("%Y-%m"),
            predicted=float(row.yhat),
            lower=float(row.yhat_lower),
            upper=float(row.yhat_upper),
        )
        for row in tail.itertuples()
    ]

    return ForecastResult(
        horizon_months=horizon_months,
        points=points,
        mode="prophet",
        note=f"Prophet forecast based on {len(monthly_totals)} months of history.",
    )
