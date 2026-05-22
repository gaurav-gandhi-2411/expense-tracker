from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import httpx
import pytest

from app.config import Settings
from app.llm import LLMClient, LLMError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings() -> Settings:
    """Build a Settings object without reading .env."""
    return Settings(
        groq_api_key="test-key",
        llm_model="primary",
        llm_fallback_model="fallback",
    )


def _make_response(content: str) -> MagicMock:
    """Build a fake Groq chat completion response containing *content*."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _make_rate_limit_error() -> Exception:
    """Construct a real groq.RateLimitError (requires a valid httpx.Request)."""
    import groq

    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(429, request=request)
    return groq.RateLimitError(message="rate limited", response=response, body=None)


def _make_none_content_response() -> MagicMock:
    """Build a fake Groq response whose first choice has content=None."""
    msg = MagicMock()
    msg.content = None
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _make_fake_client(*side_effects: object) -> MagicMock:
    """Return a fake Groq client whose create() cycles through *side_effects*.

    Each element is either a return value (MagicMock) or an exception instance.
    """
    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = list(side_effects)
    return fake_client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLLMClientChat:

    def test_chat_happy_path(self) -> None:
        """Primary model returns successfully on the first call."""
        ok_response = _make_response("hello world")
        fake_client = _make_fake_client(ok_response)
        llm = LLMClient(settings=_make_settings(), client=fake_client)

        result = llm.chat([{"role": "user", "content": "hi"}])

        assert result == "hello world"
        assert fake_client.chat.completions.create.call_count == 1
        fake_client.chat.completions.create.assert_called_once_with(
            model="primary",
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.2,
        )

    def test_chat_retries_primary_on_rate_limit(self) -> None:
        """First primary call hits RateLimitError; second primary call succeeds."""
        ok_response = _make_response("retry worked")
        rate_err = _make_rate_limit_error()
        fake_client = _make_fake_client(rate_err, ok_response)
        llm = LLMClient(settings=_make_settings(), client=fake_client)

        # Patch out the sleep so tests run instantly.
        with patch("app.llm.time.sleep"):
            result = llm.chat([{"role": "user", "content": "hi"}])

        assert result == "retry worked"
        assert fake_client.chat.completions.create.call_count == 2
        calls = fake_client.chat.completions.create.call_args_list
        # Both calls must use the primary model.
        expected = call(
            model="primary",
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.2,
        )
        assert calls[0] == expected
        assert calls[1] == expected

    def test_chat_falls_back_after_primary_exhausted(self) -> None:
        """Primary raises RateLimitError twice; fallback succeeds on third call."""
        ok_response = _make_response("fallback answer")
        rate_err_1 = _make_rate_limit_error()
        rate_err_2 = _make_rate_limit_error()
        fake_client = _make_fake_client(rate_err_1, rate_err_2, ok_response)
        llm = LLMClient(settings=_make_settings(), client=fake_client)

        with patch("app.llm.time.sleep"):
            result = llm.chat([{"role": "user", "content": "hi"}])

        assert result == "fallback answer"
        assert fake_client.chat.completions.create.call_count == 3
        calls = fake_client.chat.completions.create.call_args_list
        assert calls[0].kwargs["model"] == "primary"
        assert calls[1].kwargs["model"] == "primary"
        assert calls[2].kwargs["model"] == "fallback"

    def test_chat_raises_llm_error_when_all_attempts_fail(self) -> None:
        """Primary fails twice, fallback also fails — LLMError raised with full attempt log."""
        import groq

        rate_err_1 = _make_rate_limit_error()
        rate_err_2 = _make_rate_limit_error()

        # Use a connection error for the fallback to ensure different error types are handled.
        request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
        fallback_err = groq.APIConnectionError(request=request)

        fake_client = _make_fake_client(rate_err_1, rate_err_2, fallback_err)
        llm = LLMClient(settings=_make_settings(), client=fake_client)

        with patch("app.llm.time.sleep"), pytest.raises(LLMError) as exc_info:
            llm.chat([{"role": "user", "content": "hi"}])

        err = exc_info.value
        # Three attempts logged: primary, primary (retry), fallback.
        assert err.attempts == ["primary", "primary", "fallback"]
        assert err.cause is fallback_err

    def test_chat_passes_json_mode_response_format(self) -> None:
        """json_mode=True must pass response_format={"type": "json_object"} to the SDK."""
        ok_response = _make_response('{"amount": 10}')
        fake_client = _make_fake_client(ok_response)
        llm = LLMClient(settings=_make_settings(), client=fake_client)

        result = llm.chat([{"role": "user", "content": "parse"}], json_mode=True)

        assert result == '{"amount": 10}'
        fake_client.chat.completions.create.assert_called_once_with(
            model="primary",
            messages=[{"role": "user", "content": "parse"}],
            temperature=0.2,
            response_format={"type": "json_object"},
        )

    def test_chat_treats_none_content_as_error_and_falls_back(self) -> None:
        """Primary succeeds on attempt 1; attempt 2 (retry) returns content=None which raises
        _EmptyContentError — caught by the except APIError arm — so chat() falls through to
        the fallback model, which returns real content."""
        none_response = _make_none_content_response()
        fallback_response = _make_response("fallback answer")
        rate_err = _make_rate_limit_error()
        # Attempt 1: rate-limit (triggers retry path). Attempt 2: None-content (_EmptyContentError
        # caught by except APIError). Attempt 3: fallback succeeds.
        fake_client = _make_fake_client(rate_err, none_response, fallback_response)
        llm = LLMClient(settings=_make_settings(), client=fake_client)

        with patch("app.llm.time.sleep"):
            result = llm.chat([{"role": "user", "content": "hi"}])

        assert result == "fallback answer"
        assert fake_client.chat.completions.create.call_count == 3
        calls = fake_client.chat.completions.create.call_args_list
        # Attempt 1 and 2 use primary; attempt 3 uses fallback.
        assert calls[0].kwargs["model"] == "primary"
        assert calls[1].kwargs["model"] == "primary"
        assert calls[2].kwargs["model"] == "fallback"
