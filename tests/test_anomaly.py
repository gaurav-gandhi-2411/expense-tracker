"""Tests for app.ml.anomaly — all synthetic data, no DB, no real models besides IsolationForest."""

from __future__ import annotations

from datetime import date

from app.ml.anomaly import ExpensePoint, _build_reason, detect_anomalies

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_food_points(
    n: int,
    amount_start: float = 100.0,
    amount_step: float = 5.0,
    id_offset: int = 0,
) -> list[ExpensePoint]:
    """Return *n* ExpensePoints in category 'food' with amounts in a tight band."""
    return [
        ExpensePoint(
            id=id_offset + i + 1,
            amount=amount_start + (i % 10) * amount_step,
            category="food",
            occurred_at=date(2024, 1, (i % 28) + 1),
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDetectAnomaliesThreshold:
    def test_detect_anomalies_returns_empty_below_threshold(self) -> None:
        """With fewer than min_anomaly_samples (default 20) expenses, returns []."""
        points = _make_food_points(5)
        result = detect_anomalies(points)
        assert result == []

    def test_detect_anomalies_returns_empty_on_empty_input(self) -> None:
        """Empty input returns empty list without raising."""
        result = detect_anomalies([])
        assert result == []


class TestDetectAnomaliesOutlierDetection:
    def test_detect_anomalies_flags_obvious_outlier(self) -> None:
        """A 10 000-rupee 'food' expense amid a 100-200 band must be flagged."""
        normal_points = _make_food_points(24, amount_start=100.0, amount_step=5.0)
        outlier = ExpensePoint(
            id=999,
            amount=10_000.0,
            category="food",
            occurred_at=date(2024, 1, 15),
        )
        points = normal_points + [outlier]

        flags = detect_anomalies(points)

        outlier_ids = {f.expense_id for f in flags}
        assert outlier.id in outlier_ids, (
            f"Outlier id={outlier.id} not in flagged ids {outlier_ids}"
        )

        outlier_flag = next(f for f in flags if f.expense_id == outlier.id)
        assert outlier_flag.reason, "reason must be a non-empty string"
        assert "food" in outlier_flag.reason or "x your typical" in outlier_flag.reason, (
            f"Expected reason to mention 'food' or 'x your typical', got: {outlier_flag.reason!r}"
        )
        assert outlier_flag.score > 0, (
            f"score must be positive (negated IsolationForest score), got {outlier_flag.score}"
        )

    def test_detect_anomalies_returns_flags_sorted_by_score_descending(self) -> None:
        """Returned flags must be sorted most-anomalous first."""
        normal_points = _make_food_points(22, amount_start=100.0, amount_step=5.0)
        mild_outlier = ExpensePoint(
            id=900, amount=800.0, category="food", occurred_at=date(2024, 2, 1)
        )
        extreme_outlier = ExpensePoint(
            id=901, amount=50_000.0, category="food", occurred_at=date(2024, 2, 2)
        )
        points = normal_points + [mild_outlier, extreme_outlier]

        flags = detect_anomalies(points)

        assert len(flags) >= 1, "Expected at least one flag"
        for i in range(len(flags) - 1):
            assert flags[i].score >= flags[i + 1].score, (
                f"Score not descending at index {i}: {flags[i].score} < {flags[i+1].score}"
            )


class TestDetectAnomaliesReasonBranches:
    def test_detect_anomalies_reason_handles_rare_category_via_helper(self) -> None:
        """_build_reason directly unit-tested for rare-category branch."""
        # category_frequency < 0.05 triggers the rare-category reason
        reason = _build_reason(
            amount=120.0,
            category="gardening",
            category_mean=115.0,
            category_frequency=0.03,
        )
        assert "rare" in reason or "gardening" in reason, (
            f"Expected 'rare' or 'gardening' in reason, got: {reason!r}"
        )

    def test_build_reason_high_amount_branch(self) -> None:
        """_build_reason returns multiplier string when amount > 1.5x category mean."""
        reason = _build_reason(
            amount=300.0,
            category="food",
            category_mean=100.0,
            category_frequency=0.4,
        )
        assert "x your typical food spend" in reason, (
            f"Expected multiplier reason, got: {reason!r}"
        )
        # Should report 3.0x
        assert reason.startswith("3.0x"), f"Expected '3.0x ...', got: {reason!r}"

    def test_build_reason_generic_fallback(self) -> None:
        """_build_reason returns the generic fallback when neither special branch fires."""
        reason = _build_reason(
            amount=110.0,
            category="food",
            category_mean=100.0,
            category_frequency=0.4,
        )
        assert "unusual" in reason and "food" in reason, (
            f"Expected generic fallback, got: {reason!r}"
        )


class TestDetectAnomaliesReproducibility:
    def test_detect_anomalies_uses_seed_for_reproducibility(self) -> None:
        """Two identical calls must return bit-for-bit identical results."""
        normal_points = _make_food_points(22, amount_start=100.0, amount_step=5.0)
        outlier = ExpensePoint(
            id=999, amount=10_000.0, category="food", occurred_at=date(2024, 3, 1)
        )
        transport = ExpensePoint(
            id=998, amount=150.0, category="transport", occurred_at=date(2024, 3, 2)
        )
        points = normal_points + [outlier, transport]

        result_a = detect_anomalies(points)
        result_b = detect_anomalies(points)

        assert result_a == result_b, (
            "detect_anomalies must be deterministic; got different results on identical input"
        )
