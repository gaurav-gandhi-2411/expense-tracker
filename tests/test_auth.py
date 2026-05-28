from __future__ import annotations

import time

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.auth import get_current_user_id

TEST_SECRET = "test-jwt-secret-phase-3a"
TEST_USER_ID = "00000000-0000-0000-0000-000000000099"


def _make_token(
    user_id: str = TEST_USER_ID,
    secret: str = TEST_SECRET,
    exp_offset: int = 3600,
) -> str:
    payload = {"sub": user_id, "exp": int(time.time()) + exp_offset}
    return jwt.encode(payload, secret, algorithm="HS256")


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.fixture(autouse=True)
def _patch_jwt_secret(monkeypatch):
    """Patch SUPABASE_JWT_SECRET and clear the lru_cache for every test in this module."""
    from app import config

    config.get_settings.cache_clear()
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_SECRET)
    yield
    config.get_settings.cache_clear()


def test_valid_jwt_extracts_user_id():
    token = _make_token()
    user_id = get_current_user_id(_creds(token))
    assert user_id == TEST_USER_ID


def test_missing_token_raises_401():
    with pytest.raises(HTTPException) as exc_info:
        get_current_user_id(None)
    assert exc_info.value.status_code == 401


def test_invalid_token_raises_401():
    with pytest.raises(HTTPException) as exc_info:
        get_current_user_id(_creds("not.a.valid.token"))
    assert exc_info.value.status_code == 401


def test_expired_token_raises_401():
    token = _make_token(exp_offset=-1)  # already expired
    with pytest.raises(HTTPException) as exc_info:
        get_current_user_id(_creds(token))
    assert exc_info.value.status_code == 401


def test_wrong_secret_raises_401():
    token = _make_token(secret="wrong-secret")
    with pytest.raises(HTTPException) as exc_info:
        get_current_user_id(_creds(token))
    assert exc_info.value.status_code == 401
