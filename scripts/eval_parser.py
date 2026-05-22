"""Manual eval harness: run the parser against the 8 canonical spec cases using the real LLM."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

# Insert project root so `from app.*` imports work when run as `python scripts/eval_parser.py`
# (running as a script adds scripts/ to sys.path, not the project root).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.llm import LLMError  # noqa: E402
from app.parser import parse_expense_text  # noqa: E402


@dataclass(frozen=True)
class EvalCase:
    text: str
    expected_category: str
    expected_amount: float


CASES: list[EvalCase] = [
    EvalCase("lunch with Bob at Bombay Brasserie, 850", "food", 850.0),
    EvalCase("uber to office 240", "transport", 240.0),
    EvalCase("₹1500 for groceries yesterday", "groceries", 1500.0),
    EvalCase("electricity bill 2340", "utilities", 2340.0),
    EvalCase("netflix 649", "entertainment", 649.0),
    EvalCase("medicine 280", "health", 280.0),
    EvalCase("5000 rent", "rent", 5000.0),
    EvalCase("coffee 180", "food", 180.0),
]


@dataclass
class CaseResult:
    text: str
    expected_category: str
    expected_amount: float
    got_category: str | None
    got_amount: float | None
    confidence: float | None
    status: str  # "pass", "fail", or "error"
    diff: str  # empty string on pass


def _evaluate_case(case: EvalCase) -> CaseResult:
    """Run a single eval case and return a structured CaseResult."""
    try:
        result = parse_expense_text(case.text)
    except LLMError as exc:
        return CaseResult(
            text=case.text,
            expected_category=case.expected_category,
            expected_amount=case.expected_amount,
            got_category=None,
            got_amount=None,
            confidence=None,
            status="error",
            diff=str(exc),
        )

    category_match = result.category.lower() == case.expected_category.lower()
    amount_match = result.amount == case.expected_amount

    if category_match and amount_match:
        status = "pass"
        diff = ""
    else:
        status = "fail"
        mismatches: list[str] = []
        if not category_match:
            mismatches.append("category mismatch")
        if not amount_match:
            mismatches.append("amount mismatch")
        diff = ", ".join(mismatches)

    return CaseResult(
        text=case.text,
        expected_category=case.expected_category,
        expected_amount=case.expected_amount,
        got_category=result.category,
        got_amount=result.amount,
        confidence=result.confidence,
        status=status,
        diff=diff,
    )


def _print_case_result(cr: CaseResult) -> None:
    """Print one formatted line per case result to stdout."""
    label = f"[{cr.status.upper()}]"
    # Truncate long text to keep lines readable on narrow terminals.
    short_text = cr.text if len(cr.text) <= 40 else cr.text[:37] + "..."

    if cr.status == "error":
        print(f"{label} text={short_text!r}  error: {cr.diff}")
        return

    expected = f"{cr.expected_category}/{cr.expected_amount}"
    got = f"{cr.got_category}/{cr.got_amount}"
    conf_str = f"confidence={cr.confidence:.2f}" if cr.confidence is not None else ""
    diff_str = f"  diff: {cr.diff}" if cr.diff else ""
    print(f"{label} text={short_text!r}  expected={expected}  got={got}  {conf_str}{diff_str}")


def run_eval() -> dict[str, object]:
    """Run all CASES through the parser and return a structured summary dict.

    Prints a per-case line and a final summary to stdout as a side effect.
    The returned dict is JSON-serialisable and suitable for programmatic use.
    """
    results: list[CaseResult] = []
    for case in CASES:
        cr = _evaluate_case(case)
        _print_case_result(cr)
        results.append(cr)

    passed = sum(1 for r in results if r.status == "pass")
    failed = sum(1 for r in results if r.status == "fail")
    errored = sum(1 for r in results if r.status == "error")
    total = len(results)

    print(f"\nSummary: {passed}/{total} passed, {failed} failed, {errored} errors")

    return {
        "passed": passed,
        "failed": failed,
        "errored": errored,
        "total": total,
        "cases": [asdict(r) for r in results],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the LLM parser against the 8 canonical spec cases."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        # When --json is set, the human-readable output is still printed first,
        # then the JSON dump follows. This lets you pipe to jq while still
        # seeing the per-case lines in the terminal.
        help="Also emit the full result as JSON after the human-readable output.",
    )
    args = parser.parse_args()
    result = run_eval()
    if args.json:
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
