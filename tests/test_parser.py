from __future__ import annotations

import json
from datetime import date
from unittest.mock import MagicMock

import pytest

from app.llm import LLMError
from app.parser import extract_category, parse_expense_text
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


# ---------------------------------------------------------------------------
# extract_category tests
# ---------------------------------------------------------------------------


def _mock_category_llm(raw_response: str) -> MagicMock:
    """Return a MagicMock whose .chat() returns *raw_response* (plain string, not JSON)."""
    mock = MagicMock()
    mock.chat.return_value = raw_response
    return mock


def test_extract_category_food() -> None:
    """'swiggy order 480' — model returns 'food'."""
    mock_llm = _mock_category_llm("food")
    assert extract_category("swiggy order 480", llm=mock_llm) == "food"


def test_extract_category_transport() -> None:
    """'uber to office 240' — model returns 'transport'."""
    mock_llm = _mock_category_llm("transport")
    assert extract_category("uber to office 240", llm=mock_llm) == "transport"


def test_extract_category_entertainment() -> None:
    """'netflix 649' — model returns 'entertainment'."""
    mock_llm = _mock_category_llm("entertainment")
    assert extract_category("netflix 649", llm=mock_llm) == "entertainment"


def test_extract_category_utilities() -> None:
    """'electricity bill 2340' — model returns 'utilities'."""
    mock_llm = _mock_category_llm("utilities")
    assert extract_category("electricity bill 2340", llm=mock_llm) == "utilities"


def test_extract_category_normalises_messy_response() -> None:
    """Model returns 'Food.\\n' — normalisation strips punctuation/whitespace to 'food'."""
    mock_llm = _mock_category_llm("Food.\n")
    assert extract_category("swiggy order 480", llm=mock_llm) == "food"


def test_extract_category_uses_plain_mode() -> None:
    """extract_category must call llm.chat with json_mode=False and temperature=0.0."""
    mock_llm = _mock_category_llm("food")

    extract_category("coffee 180", llm=mock_llm)

    mock_llm.chat.assert_called_once()
    _, kwargs = mock_llm.chat.call_args
    assert kwargs.get("json_mode") is False
    assert kwargs.get("temperature") == 0.0


def test_extract_category_propagates_llm_error() -> None:
    """LLMError raised by the client propagates unchanged to the caller."""
    mock_llm = MagicMock()
    mock_llm.chat.side_effect = LLMError("all attempts failed", attempts=["m1", "m2"])

    with pytest.raises(LLMError):
        extract_category("coffee 180", llm=mock_llm)
