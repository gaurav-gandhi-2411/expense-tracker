from __future__ import annotations

import json
from datetime import date
from unittest.mock import MagicMock

import pytest

from app.llm import LLMError
from app.parser import parse_expense_text
from app.schemas import ParsedExpense

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TODAY = date.today().isoformat()
YESTERDAY = date.fromordinal(date.today().toordinal() - 1).isoformat()


def _mock_llm(json_payload: str) -> MagicMock:
    """Return a MagicMock whose .chat() returns *json_payload*."""
    mock = MagicMock()
    mock.chat.return_value = json_payload
    return mock


def _canned(
    amount: float,
    category: str,
    description: str,
    occurred_at: str = TODAY,
    confidence: float = 0.9,
) -> str:
    """Serialise a canned ParsedExpense JSON payload."""
    return json.dumps(
        {
            "amount": amount,
            "category": category,
            "description": description,
            "occurred_at": occurred_at,
            "confidence": confidence,
        }
    )


# ---------------------------------------------------------------------------
# Parametrized happy-path tests (8 spec cases)
# ---------------------------------------------------------------------------

_HAPPY_CASES: list[tuple[str, str, float, str]] = [
    # (input_text, expected_category, expected_amount, canned_json)
    (
        "lunch with Bob at Bombay Brasserie, 850",
        "food",
        850.0,
        _canned(850.0, "food", "Lunch at Bombay Brasserie"),
    ),
    (
        "uber to office 240",
        "transport",
        240.0,
        _canned(240.0, "transport", "Uber to office"),
    ),
    (
        "₹1500 for groceries yesterday",
        "groceries",
        1500.0,
        _canned(1500.0, "groceries", "Groceries", occurred_at=YESTERDAY),
    ),
    (
        "electricity bill 2340",
        "utilities",
        2340.0,
        _canned(2340.0, "utilities", "Electricity bill"),
    ),
    (
        "netflix 649",
        "entertainment",
        649.0,
        _canned(649.0, "entertainment", "Netflix subscription"),
    ),
    (
        "medicine 280",
        "health",
        280.0,
        _canned(280.0, "health", "Medicine"),
    ),
    (
        "5000 rent",
        "rent",
        5000.0,
        _canned(5000.0, "rent", "Rent payment"),
    ),
    (
        "coffee 180",
        "food",
        180.0,
        _canned(180.0, "food", "Coffee"),
    ),
]


@pytest.mark.parametrize(
    "text,expected_category,expected_amount,canned_json",
    _HAPPY_CASES,
    ids=[row[0][:30] for row in _HAPPY_CASES],
)
def test_parse_expense_happy_path(
    text: str,
    expected_category: str,
    expected_amount: float,
    canned_json: str,
) -> None:
    """parse_expense_text returns a correctly validated ParsedExpense for each spec row."""
    mock_llm = _mock_llm(canned_json)

    result = parse_expense_text(text, llm=mock_llm)

    assert isinstance(result, ParsedExpense)
    assert result.category == expected_category
    assert result.amount == expected_amount
    assert 0.0 <= result.confidence <= 1.0
    assert isinstance(result.occurred_at, date)


# ---------------------------------------------------------------------------
# Error-path tests (3 explicit cases)
# ---------------------------------------------------------------------------


def test_parser_raises_llm_error_on_malformed_json() -> None:
    """Non-JSON response from LLM triggers LLMError whose cause is a JSONDecodeError."""
    import json as _json

    mock_llm = _mock_llm("not json {")

    with pytest.raises(LLMError) as exc_info:
        parse_expense_text("coffee 180", llm=mock_llm)

    err = exc_info.value
    assert isinstance(err.cause, _json.JSONDecodeError)


def test_parser_raises_llm_error_on_invalid_schema() -> None:
    """JSON missing required 'amount' field triggers LLMError whose cause is ValidationError."""
    import pydantic

    bad_json = json.dumps(
        {"category": "food", "description": "Coffee", "occurred_at": TODAY, "confidence": 0.9}
    )
    mock_llm = _mock_llm(bad_json)

    with pytest.raises(LLMError) as exc_info:
        parse_expense_text("coffee 180", llm=mock_llm)

    err = exc_info.value
    assert isinstance(err.cause, pydantic.ValidationError)


def test_parser_passes_json_mode_to_llm() -> None:
    """parse_expense_text must call llm.chat with json_mode=True and temperature=0.0."""
    mock_llm = _mock_llm(_canned(180.0, "food", "Coffee"))

    parse_expense_text("coffee 180", llm=mock_llm)

    mock_llm.chat.assert_called_once()
    _, kwargs = mock_llm.chat.call_args
    assert kwargs.get("json_mode") is True
    assert kwargs.get("temperature") == 0.0
