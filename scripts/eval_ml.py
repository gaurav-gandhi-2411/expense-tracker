"""Manual eval harness for Phase 2 local ML features.

Loads the real sentence-transformers embedding model and runs three sequential
evaluation sections against live data:

  1. Categorizer — zero-shot accuracy on the 8 canonical parser spec cases.
  2. Anomaly     — IsolationForest flags on real seeded DB data.
  3. Forecast    — Prophet (or fallback) monthly spend projection.

NOT for CI.  Run manually after model or data changes:

    python scripts/eval_ml.py
    python scripts/eval_ml.py --skip-anomaly --skip-forecast
    python scripts/eval_ml.py --skip-categorizer

Requires a populated DB for anomaly/forecast sections — run ``python scripts/seed.py`` first.
The categorizer section has no DB dependency and works offline after the first model download.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Insert project root so ``from app.*`` imports work when invoked as
# ``python scripts/eval_ml.py`` (which adds scripts/ to sys.path, not the project root).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---------------------------------------------------------------------------
# Categorizer eval
# ---------------------------------------------------------------------------

# The 8 canonical cases from the Phase 1 parser spec — text + expected category.
# Defined inline to avoid coupling to eval_parser.py.
_CATEGORIZER_CASES: list[tuple[str, str]] = [
    ("lunch with Bob at Bombay Brasserie, 850", "food"),
    ("uber to office 240", "transport"),
    ("₹1500 for groceries yesterday", "groceries"),
    ("electricity bill 2340", "utilities"),
    ("netflix 649", "entertainment"),
    ("medicine 280", "health"),
    ("5000 rent", "rent"),
    ("coffee 180", "food"),
]

# A superset of the expected categories plus a few distractors.
# The eval uses this as the prototype list for zero-shot similarity matching.
_PROTOTYPES: list[str] = [
    "food",
    "transport",
    "groceries",
    "utilities",
    "entertainment",
    "health",
    "rent",
    "other",
    "travel",
    "subscription",
]


def eval_categorizer() -> None:
    """Run zero-shot categorizer on the 8 canonical spec cases and print per-case results.

    Imports ``suggest_category`` from the categorizer module; the real embedding
    model is loaded lazily on the first call (may be slow on cold start).
    """
    from app.ml.categorizer import suggest_category  # noqa: PLC0415

    print("=" * 70)
    print("SECTION 1: Categorizer eval (zero-shot, 8 canonical cases)")
    print("=" * 70)

    passed = 0
    total = len(_CATEGORIZER_CASES)

    for text, expected in _CATEGORIZER_CASES:
        result = suggest_category(text, _PROTOTYPES)
        ok = result.category.lower() == expected.lower()
        if ok:
            passed += 1
        label = "pass" if ok else "fail"
        # Truncate long text so lines stay within 100 chars.
        short = text if len(text) <= 45 else text[:42] + "..."
        print(
            f"[{label}] text={short!r}  expected={expected}"
            f"  got={result.category}  score={result.score:.2f}"
        )

    pct = 100 * passed / total
    print(f"\nCategorizer accuracy: {passed}/{total} ({pct:.0f}%)\n")


# ---------------------------------------------------------------------------
# Anomaly eval
# ---------------------------------------------------------------------------


def eval_anomaly() -> None:
    """Run IsolationForest anomaly detection on all expenses in the live DB.

    Requires at least ``min_anomaly_samples`` (default 20) rows — run
    ``python scripts/seed.py`` first if the DB is empty.
    """
    from app.config import get_settings  # noqa: PLC0415
    from app.db import SessionLocal  # noqa: PLC0415
    from app.ml.anomaly import ExpensePoint, detect_anomalies  # noqa: PLC0415
    from app.models import Expense  # noqa: PLC0415

    print("=" * 70)
    print("SECTION 2: Anomaly eval (IsolationForest on live DB)")
    print("=" * 70)

    session = SessionLocal()
    try:
        rows = session.query(Expense).all()
    finally:
        session.close()

    threshold = get_settings().min_anomaly_samples

    if not rows:
        print(
            "  [skip] DB is empty — run `python scripts/seed.py` first, then re-run this script."
        )
        print()
        return

    if len(rows) < threshold:
        print(
            f"  [skip] Only {len(rows)} expenses found; need >= {threshold} for anomaly detection."
        )
        print("  Hint: run `python scripts/seed.py` to populate ~25 deterministic fake expenses.")
        print()
        return

    points: list[ExpensePoint] = [
        ExpensePoint(
            id=row.id,
            amount=row.amount,
            category=row.category,
            occurred_at=row.occurred_at,
        )
        for row in rows
    ]

    flags = detect_anomalies(points)

    if not flags:
        print(f"  No anomalies flagged across {len(points)} expenses.")
    else:
        print(f"  Flagged {len(flags)} anomalies out of {len(points)} expenses:\n")
        for flag in flags:
            print(
                f"    id={flag.expense_id}  amount=₹{flag.amount:,.2f}"
                f"  category={flag.category}"
                f"  score={flag.score:.4f}  reason={flag.reason!r}"
            )

    print(f"\nAnomaly summary: {len(flags)} flagged / {len(points)} total\n")


# ---------------------------------------------------------------------------
# Forecast eval
# ---------------------------------------------------------------------------


def eval_forecast() -> None:
    """Run spend forecast on real monthly aggregates from the live DB.

    Prints the forecast mode, explanatory note, and each projected month.
    If ``mode == "low-confidence-average"`` that is surfaced prominently.
    Requires a populated DB — run ``python scripts/seed.py`` first.
    """
    from app.db import SessionLocal  # noqa: PLC0415
    from app.ml.forecast import forecast_spend  # noqa: PLC0415
    from app.stats import total_by_month  # noqa: PLC0415

    print("=" * 70)
    print("SECTION 3: Forecast eval (Prophet / fallback, 3-month horizon)")
    print("=" * 70)

    session = SessionLocal()
    try:
        monthly = total_by_month(session)
    finally:
        session.close()

    if not monthly:
        print(
            "  [skip] No monthly data in DB — run `python scripts/seed.py` first."
        )
        print()
        return

    monthly_tuples: list[tuple[str, float]] = [(r.month, r.total) for r in monthly]

    result = forecast_spend(monthly_tuples, horizon_months=3)

    if result.mode == "low-confidence-average":
        print(f"  *** LOW CONFIDENCE: {result.note} ***")
    else:
        print(f"  mode : {result.mode}")
        print(f"  note : {result.note}")

    print()
    for pt in result.points:
        print(
            f"  {pt.month}  predicted=₹{pt.predicted:,.2f}"
            f"  lower=₹{pt.lower:,.2f}  upper=₹{pt.upper:,.2f}"
        )

    print(f"\nForecast summary: {result.horizon_months}-month horizon, mode={result.mode}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Parse CLI flags and run enabled eval sections sequentially."""
    parser = argparse.ArgumentParser(
        description=(
            "Manual eval harness for Phase 2 local ML features. "
            "Loads real models — NOT for CI. "
            "Run `python scripts/seed.py` first for anomaly/forecast sections."
        )
    )
    parser.add_argument(
        "--skip-categorizer",
        action="store_true",
        help="Skip the zero-shot categorizer eval section.",
    )
    parser.add_argument(
        "--skip-anomaly",
        action="store_true",
        help="Skip the IsolationForest anomaly eval section.",
    )
    parser.add_argument(
        "--skip-forecast",
        action="store_true",
        help="Skip the Prophet forecast eval section.",
    )
    args = parser.parse_args()

    if not args.skip_categorizer:
        eval_categorizer()
    if not args.skip_anomaly:
        eval_anomaly()
    if not args.skip_forecast:
        eval_forecast()


if __name__ == "__main__":
    main()
