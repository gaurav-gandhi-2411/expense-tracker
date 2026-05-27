from __future__ import annotations

import json
import re
from datetime import date

import pydantic

from app.llm import LLMClient, LLMError
from app.schemas import ParsedExpense

# System prompt template. {today} is substituted at call time so relative
# dates like "yesterday" resolve correctly against the actual wall-clock date.
_SYSTEM_PROMPT_TEMPLATE = (
    "You extract expense details from free-form text and return ONLY a JSON object.\n"
    "\n"
    "Today is {today}.\n"
    "\n"
    "Return exactly this shape:\n"
    '{{"amount": <number>, "category": <string>, "description": <string>, '
    '"occurred_at": "<YYYY-MM-DD>", "confidence": <0-1>}}\n'
    "\n"
    "Rules:\n"
    "- amount: positive number (strip currency symbols)\n"
    "- category: one of food, transport, groceries, utilities, entertainment, "
    "health, rent, shopping, other\n"
    "- description: concise label for the expense\n"
    '- occurred_at: ISO date; resolve "yesterday"/"today" relative to today above; '
    "default to today if no date given\n"
    "- confidence: 0.9 if details are clear, 0.5 if ambiguous\n"
    "- Output JSON only. No markdown, no explanation."
)


def parse_expense_text(text: str, *, llm: LLMClient | None = None) -> ParsedExpense:
    """Parse free-form expense text into a structured ParsedExpense via an LLM.

    Args:
        text: Human-readable expense description, e.g. "lunch with Bob 850".
        llm:  Optional pre-constructed LLMClient; a default instance is created
              when None (uses cached settings from get_settings()).

    Returns:
        A validated ParsedExpense instance.

    Raises:
        LLMError: If the LLM returns malformed JSON or a JSON payload that does
                  not satisfy the ParsedExpense schema.
    """
    if llm is None:
        llm = LLMClient()

    system_content = _SYSTEM_PROMPT_TEMPLATE.format(today=date.today().isoformat())
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": text},
    ]

    raw = llm.chat(messages, json_mode=True, temperature=0.0)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as json_err:
        raise LLMError(
            "LLM returned malformed JSON",
            attempts=["parse"],
            cause=json_err,
        ) from json_err

    try:
        return ParsedExpense.model_validate(data)
    except pydantic.ValidationError as val_err:
        raise LLMError(
            "LLM JSON did not match ParsedExpense schema",
            attempts=["parse"],
            cause=val_err,
        ) from val_err


_CATEGORY_SYSTEM_PROMPT = (
    "You are an expense categoriser. Given a freeform expense note, respond with ONLY the "
    "single best-fit category as one lowercase word. No punctuation, no explanation.\n"
    "\n"
    "Choose from: food, transport, groceries, utilities, entertainment, health, rent, other.\n"
    "If none fit well, respond with: other"
)


def extract_category(text: str, *, llm: LLMClient | None = None) -> str:
    """Return the best-fit expense category for *text* as a single lowercase word.

    Calls the LLM with a lightweight single-purpose prompt. The returned string
    is lowercased and stripped of surrounding whitespace and punctuation, but is
    NOT remapped to "other" when the model returns an out-of-vocabulary token —
    that decision belongs to the caller.

    Args:
        text: Freeform expense note, e.g. "uber to office 240".
        llm:  Optional pre-constructed LLMClient; a default instance is created
              when None.

    Returns:
        Cleaned category string (lowercase, no surrounding punctuation/whitespace).

    Raises:
        LLMError: Propagated from LLMClient.chat() if all retry/fallback attempts fail.
    """
    if llm is None:
        llm = LLMClient()

    messages: list[dict[str, str]] = [
        {"role": "system", "content": _CATEGORY_SYSTEM_PROMPT},
        {"role": "user", "content": text},
    ]

    raw = llm.chat(messages, json_mode=False, temperature=0.0)
    return re.sub(r"[^\w]", "", raw.strip().lower())
