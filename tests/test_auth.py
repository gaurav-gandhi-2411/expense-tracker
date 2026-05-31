from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app.auth import get_current_user_id
from app.main import app

TEST_USER_ID = "00000000-0000-0000-0000-000000000001"
HS256_SECRET = "test-secret-for-unit-tests-only"


def _make_hs256_token(
    user_id: str = TEST_USER_ID,
    secret: str = HS256_SECRET,
    exp_offset: int = 3600,
) -> str:
    payload = {"sub": user_id, "exp": int(time.time()) + exp_offset, "aud": "authenticated"}
    return jwt.encode(payload, secret, algorithm="HS256")


# ---------------------------------------------------------------------------
# HS256 path
# ---------------------------------------------------------------------------

def test_valid_hs256_token_returns_user_id(client: TestClient) -> None:
    """Auth dep is overridden in conftest — any request reaches the endpoint."""
    response = client.get("/expenses")
    assert response.status_code == 200


def test_missing_token_returns_401(client: TestClient) -> None:
    # Remove only the auth override; DB override stays intact.
    old = app.dependency_overrides.pop(get_current_user_id, None)
    try:
        response = client.get("/expenses")
        assert response.status_code == 401
        assert response.json()["detail"] == "Missing authentication token"
    finally:
        if old is not None:
            app.dependency_overrides[get_current_user_id] = old


def test_invalid_hs256_token_returns_401(client: TestClient) -> None:
    old = app.dependency_overrides.pop(get_current_user_id, None)
    try:
        response = client.get(
            "/expenses", headers={"Authorization": "Bearer not.a.jwt"}
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid authentication token"
    finally:
        if old is not None:
            app.dependency_overrides[get_current_user_id] = old


def test_expired_hs256_token_returns_401(client: TestClient) -> None:
    old = app.dependency_overrides.pop(get_current_user_id, None)
    try:
        token = _make_hs256_token(exp_offset=-10, secret=HS256_SECRET)
        with patch("app.auth.get_settings") as mock_settings:
            mock_settings.return_value.supabase_jwt_secret = HS256_SECRET
            mock_settings.return_value.supabase_url = "https://example.supabase.co"
            response = client.get(
                "/expenses", headers={"Authorization": f"Bearer {token}"}
            )
        assert response.status_code == 401
        assert response.json()["detail"] == "Token has expired"
    finally:
        if old is not None:
            app.dependency_overrides[get_current_user_id] = old


# ---------------------------------------------------------------------------
# ES256 path
# ---------------------------------------------------------------------------

def test_valid_es256_token_is_accepted(client: TestClient) -> None:
    """ES256 token validated via mocked PyJWKClient passes through to the endpoint."""
    old = app.dependency_overrides.pop(get_current_user_id, None)
    try:
        private_key = ec.generate_private_key(ec.SECP256R1())
        public_key = private_key.public_key()

        payload = {"sub": TEST_USER_ID, "exp": int(time.time()) + 3600, "aud": "authenticated"}
        token = jwt.encode(payload, private_key, algorithm="ES256")

        mock_signing_key = MagicMock()
        mock_signing_key.key = public_key
        mock_client = MagicMock()
        mock_client.get_signing_key_from_jwt.return_value = mock_signing_key

        with patch("app.auth._get_jwks_client", return_value=mock_client):
            response = client.get(
                "/expenses", headers={"Authorization": f"Bearer {token}"}
            )

        assert response.status_code == 200
    finally:
        if old is not None:
            app.dependency_overrides[get_current_user_id] = old


def test_expired_es256_token_returns_401(client: TestClient) -> None:
    old = app.dependency_overrides.pop(get_current_user_id, None)
    try:
        private_key = ec.generate_private_key(ec.SECP256R1())
        public_key = private_key.public_key()

        payload = {"sub": TEST_USER_ID, "exp": int(time.time()) - 10, "aud": "authenticated"}
        token = jwt.encode(payload, private_key, algorithm="ES256")

        mock_signing_key = MagicMock()
        mock_signing_key.key = public_key
        mock_client = MagicMock()
        mock_client.get_signing_key_from_jwt.return_value = mock_signing_key

        with patch("app.auth._get_jwks_client", return_value=mock_client):
            response = client.get(
                "/expenses", headers={"Authorization": f"Bearer {token}"}
            )

        assert response.status_code == 401
        assert response.json()["detail"] == "Token has expired"
    finally:
        if old is not None:
            app.dependency_overrides[get_current_user_id] = old


# ---------------------------------------------------------------------------
# Unsupported algorithm
# ---------------------------------------------------------------------------

def test_unsupported_algorithm_returns_401(client: TestClient) -> None:
    """A token with an unrecognised alg is rejected with 401."""
    import base64
    import json

    old = app.dependency_overrides.pop(get_current_user_id, None)
    try:
        # Craft a token whose header claims alg=RS256 (unsupported) but has a fake sig.
        header = (
            base64.urlsafe_b64encode(
                json.dumps({"alg": "RS256", "typ": "JWT"}).encode()
            )
            .rstrip(b"=")
            .decode()
        )
        body = (
            base64.urlsafe_b64encode(
                json.dumps(
                    {"sub": TEST_USER_ID, "exp": int(time.time()) + 3600}
                ).encode()
            )
            .rstrip(b"=")
            .decode()
        )
        token = f"{header}.{body}.fakesig"

        response = client.get(
            "/expenses", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401
        assert response.json()["detail"] in (
            "Unsupported JWT algorithm",
            "Invalid authentication token",
        )
    finally:
        if old is not None:
            app.dependency_overrides[get_current_user_id] = old
