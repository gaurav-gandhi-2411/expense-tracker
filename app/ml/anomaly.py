"""Anomaly detection for expense data using IsolationForest."""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

import numpy as np
from sklearn.ensemble import IsolationForest  # type: ignore[import-untyped]

from app.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExpensePoint:
    """A minimal expense record used as input to anomaly detection."""

    id: int
    amount: float
    category: str
    occurred_at: date


@dataclass(frozen=True)
class AnomalyFlag:
    """A single flagged expense with a human-readable reason and anomaly score."""

    expense_id: int
    amount: float
    category: str
    reason: str
    score: float  # higher == more anomalous (negated IsolationForest score_samples)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_reason(
    amount: float,
    category: str,
    category_mean: float,
    category_frequency: float,
) -> str:
    """Return a concise, user-facing reason string for a flagged expense.

    Args:
        amount:             Raw amount of the flagged expense.
        category:           Category label.
        category_mean:      Mean amount across all expenses in this category.
        category_frequency: Fraction of total expenses that share this category.

    Returns:
        A short plain-language description of why the expense looks anomalous.
    """
    if amount > 1.5 * category_mean:
        multiple = amount / category_mean if category_mean > 0 else float("inf")
        return f"{multiple:.1f}x your typical {category} spend"
    if category_frequency < 0.05:
        return f"rare category in your history ({category})"
    return f"unusual {category} expense"


def _build_feature_matrix(expenses: list[ExpensePoint]) -> np.ndarray:
    """Assemble the (n, 4) numeric feature matrix for IsolationForest.

    Features (one row per expense):
        0: amount           — raw float amount
        1: day_of_week      — int 0-6 from occurred_at.weekday()
        2: category_frequency — fraction of all expenses in this category
        3: rolling_category_mean_deviation — (amount - cat_mean) / max(cat_std, 1.0)

    Args:
        expenses: Non-empty list of ExpensePoints.

    Returns:
        Float64 numpy array of shape (len(expenses), 4).
    """
    n = len(expenses)

    # --- pre-compute per-category statistics ---
    cat_amounts: dict[str, list[float]] = defaultdict(list)
    for ep in expenses:
        cat_amounts[ep.category].append(ep.amount)

    cat_mean: dict[str, float] = {c: float(np.mean(v)) for c, v in cat_amounts.items()}
    cat_std: dict[str, float] = {c: float(np.std(v)) for c, v in cat_amounts.items()}
    cat_count: dict[str, int] = {c: len(v) for c, v in cat_amounts.items()}

    # --- assemble feature matrix ---
    X = np.zeros((n, 4), dtype=np.float64)
    for i, ep in enumerate(expenses):
        dev = (ep.amount - cat_mean[ep.category]) / max(cat_std[ep.category], 1.0)
        X[i] = [
            ep.amount,
            float(ep.occurred_at.weekday()),
            cat_count[ep.category] / n,
            dev,
        ]

    return X


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_anomalies(expenses: list[ExpensePoint]) -> list[AnomalyFlag]:
    """Detect anomalous expenses using IsolationForest.

    Returns an empty list when the sample count is below the configured
    ``min_anomaly_samples`` threshold — avoids noisy results on sparse data.

    Args:
        expenses: All expense records to analyse in a single pass.

    Returns:
        List of :class:`AnomalyFlag` sorted by ``score`` descending
        (most anomalous first).  Empty when there is insufficient data.
    """
    threshold = get_settings().min_anomaly_samples

    if len(expenses) < threshold:
        logger.info(
            "anomaly detection skipped: %d samples below threshold %d",
            len(expenses),
            threshold,
        )
        return []

    # --- feature matrix ---
    X = _build_feature_matrix(expenses)

    # --- fit and predict ---
    # contamination="auto" lets sklearn infer expected outlier fraction.
    # random_state=42 ensures deterministic results across identical inputs.
    model = IsolationForest(contamination=0.05, random_state=42)
    labels: np.ndarray = model.fit_predict(X)    # -1 = outlier, 1 = inlier
    raw_scores: np.ndarray = model.score_samples(X)  # lower == more anomalous

    # --- pre-compute category stats needed for reason strings ---
    cat_amounts: dict[str, list[float]] = defaultdict(list)
    for ep in expenses:
        cat_amounts[ep.category].append(ep.amount)
    cat_mean: dict[str, float] = {c: float(np.mean(v)) for c, v in cat_amounts.items()}
    cat_count: dict[str, int] = {c: len(v) for c, v in cat_amounts.items()}
    n = len(expenses)

    # --- collect flags for outlier rows ---
    flags: list[AnomalyFlag] = []
    for i, ep in enumerate(expenses):
        if labels[i] == -1:
            freq = cat_count[ep.category] / n
            reason = _build_reason(ep.amount, ep.category, cat_mean[ep.category], freq)
            flags.append(
                AnomalyFlag(
                    expense_id=ep.id,
                    amount=ep.amount,
                    category=ep.category,
                    reason=reason,
                    score=float(-raw_scores[i]),  # negate: higher == more anomalous
                )
            )

    flags.sort(key=lambda f: f.score, reverse=True)
    return flags
