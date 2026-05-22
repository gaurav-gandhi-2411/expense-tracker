from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from groq import APIConnectionError, APIError, Groq, RateLimitError

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Transient errors worth retrying: rate limits and connection failures.
# APIStatusError covers 5xx server errors; APIError is the broadest base.
_RETRYABLE = (RateLimitError, APIConnectionError)

# Sentinel request used only to satisfy groq.APIError's required `request` arg
# when raising _EmptyContentError — no real HTTP request is made.
_DUMMY_REQUEST = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")


class _EmptyContentError(APIError):
    """Raised by _call() when the API returns a choice with content=None.

    Subclasses APIError so chat()'s existing except-APIError fallback path
    handles it uniformly (attempt 2 non-retryable branch, or fallback branch).
    """

    def __init__(self, model: str) -> None:
        super().__init__(
            f"Model {model!r} returned a choice with content=None "
            "(possible tool-call or content-policy refusal)",
            _DUMMY_REQUEST,
            body=None,
        )


class LLMError(Exception):
    """Raised when all LLM call attempts (primary + retry + fallback) fail."""

    def __init__(
        self,
        message: str,
        *,
        attempts: list[str],
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.cause = cause


class LLMClient:
    """Thin Groq wrapper with retry-then-fallback logic."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: Groq | None = None,
    ) -> None:
        self.settings = settings if settings is not None else get_settings()
        self._client = client if client is not None else Groq(api_key=self.settings.groq_api_key)

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        json_mode: bool = False,
        temperature: float = 0.2,
    ) -> str:
        """Send a chat request, returning the text of the first choice.

        Retry flow:
        1. Try primary model.
        2. On transient error: wait 1 s, retry primary once.
        3. If primary still fails: try fallback model once.
        4. If all three attempts fail: raise LLMError with the full attempt log.
        """
        extra_kwargs: dict[str, Any] = {}
        if json_mode:
            extra_kwargs["response_format"] = {"type": "json_object"}

        primary = self.settings.llm_model
        fallback = self.settings.llm_fallback_model
        attempts: list[str] = []
        last_exc: Exception | None = None

        # --- attempt 1: primary (first try) ---
        try:
            attempts.append(primary)
            return self._call(primary, messages, temperature, extra_kwargs)
        except _RETRYABLE as exc:
            last_exc = exc
            logger.warning(
                "Primary model %s hit transient error; retrying in 1 s. error=%s",
                primary,
                exc,
            )

        # We retry primary before trying fallback because the fallback model is
        # smaller and less capable; a brief wait often resolves rate-limit bursts.
        time.sleep(1.0)

        # --- attempt 2: primary (retry) ---
        try:
            attempts.append(primary)
            return self._call(primary, messages, temperature, extra_kwargs)
        except _RETRYABLE as exc:
            last_exc = exc
            logger.warning(
                "Primary model %s still failing after retry; switching to fallback. error=%s",
                primary,
                exc,
            )
        except APIError as exc:
            last_exc = exc
            logger.warning(
                "Primary model %s non-retryable error on retry; switching to fallback. error=%s",
                primary,
                exc,
            )

        # --- attempt 3: fallback ---
        try:
            attempts.append(fallback)
            return self._call(fallback, messages, temperature, extra_kwargs)
        except APIError as exc:
            last_exc = exc
            logger.error("Fallback model %s also failed. Raising LLMError. error=%s", fallback, exc)

        raise LLMError(
            "All LLM attempts failed",
            attempts=attempts,
            cause=last_exc,
        )

    def _call(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        extra_kwargs: dict[str, Any],
    ) -> str:
        """Execute a single Groq chat completions call and return content text."""
        response = self._client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            **extra_kwargs,
        )
        content = response.choices[0].message.content
        if content is None:
            raise _EmptyContentError(model)
        return content


def get_llm_client() -> LLMClient:
    """FastAPI dependency that yields a default LLMClient. Override in tests."""
    return LLMClient()
