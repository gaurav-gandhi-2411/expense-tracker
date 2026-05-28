from __future__ import annotations

import argparse
import random
import sys
from datetime import date, timedelta
from pathlib import Path

# Insert project root so `from app.*` works when run as `python scripts/seed.py`
# (running as a script adds scripts/ to sys.path, not the project root).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import Expense  # noqa: E402

random.seed(42)

# (category, weight, amount_range, description_choices)
CATEGORY_CONFIG: list[tuple[str, int, tuple[float, float], list[str]]] = [
    ("food",          30, (100.0,   800.0),   ["lunch", "dinner", "coffee", "snacks"]),
    ("transport",     20, (50.0,    500.0),   ["auto", "metro", "cab", "bus"]),
    ("groceries",     20, (200.0,  1500.0),   ["weekly groceries", "supermarket run"]),
    ("utilities",     10, (500.0,  3000.0),   ["electricity", "internet", "water"]),
    ("entertainment", 15, (200.0,  2000.0),   ["movie", "streaming", "event"]),
    ("rent",           5, (15000.0, 30000.0), ["monthly rent"]),
]

CATEGORIES   = [c[0] for c in CATEGORY_CONFIG]
WEIGHTS      = [c[1] for c in CATEGORY_CONFIG]
AMOUNT_RANGE = {c[0]: c[2] for c in CATEGORY_CONFIG}
DESCRIPTIONS = {c[0]: c[3] for c in CATEGORY_CONFIG}

NUM_EXPENSES = 25


def _build_expenses(today: date, user_id: str) -> list[Expense]:
    """Return a list of NUM_EXPENSES unsaved Expense objects spread over the last 90 days."""
    chosen_categories = random.choices(CATEGORIES, weights=WEIGHTS, k=NUM_EXPENSES)
    expenses: list[Expense] = []
    for cat in chosen_categories:
        lo, hi = AMOUNT_RANGE[cat]
        amount = round(random.uniform(lo, hi), 2)
        offset = random.randrange(0, 90)
        occurred = today - timedelta(days=offset)
        description = random.choice(DESCRIPTIONS[cat])
        expenses.append(
            Expense(
                amount=amount,
                category=cat,
                description=description,
                occurred_at=occurred,
                user_id=user_id,
            )
        )
    return expenses


def main() -> None:
    """Seed the database with deterministic fake expenses.

    --user-id: UUID to assign to all seeded expenses. Defaults to the
               deterministic local-dev UUID 00000000-0000-0000-0000-000000000001.
    """
    parser = argparse.ArgumentParser(description="Seed expense database with fake data.")
    parser.add_argument(
        "--user-id",
        default="00000000-0000-0000-0000-000000000001",
        help="User UUID to assign to seeded expenses (default: local dev UUID)",
    )
    args = parser.parse_args()
    user_id = args.user_id

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        deleted = db.query(Expense).delete()
        db.commit()
        print(f"cleared {deleted} existing rows")

        today = date.today()
        expenses = _build_expenses(today, user_id)
        for exp in expenses:
            db.add(exp)
        db.commit()

        dates = [e.occurred_at for e in expenses]
        cat_counts: dict[str, int] = {}
        for e in expenses:
            cat_counts[e.category] = cat_counts.get(e.category, 0) + 1

        print(f"inserted {len(expenses)} rows (user_id={user_id}) across categories: {cat_counts}")
        print(f"earliest: {min(dates)}  latest: {max(dates)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
