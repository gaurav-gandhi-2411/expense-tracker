from __future__ import annotations

import logging
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)

# Module-level JWKS client — PyJWKClient handles caching internally.
# Instantiated lazily on first ES256 request so it doesn't make network
# calls at import time (avoids failures in test environments).
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        jwks_url = f"{get_settings().supabase_url}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=3600)
    return _jwks_client


def _ensure_profile(db: Session, user_id: str) -> None:
    """Record first use — see app.models.AppProfile for why."""
    from app.models import AppProfile  # noqa: PLC0415 — avoids a module import cycle

    if db.get(AppProfile, user_id) is None:
        db.add(AppProfile(user_id=user_id))
        db.commit()


def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> str:
    """Validate Supabase JWT (HS256 or ES256) and return the user_id (sub claim).

    Raises HTTP 401 for missing, invalid, expired, or unsupported-algorithm tokens.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    alg = header.get("alg", "")

    try:
        if alg == "HS256":
            secret = get_settings().supabase_jwt_secret
            payload: dict = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                audience="authenticated",
                options={"require": ["sub", "exp"]},
            )
        elif alg == "ES256":
            signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256"],
                audience="authenticated",
                options={"require": ["sub", "exp"]},
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unsupported JWT algorithm",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except HTTPException:
        raise
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user_id: str = payload["sub"]
    _ensure_profile(db, user_id)
    return user_id
