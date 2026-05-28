from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_train_categorizer_returns_404_when_admin_disabled(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /ml/train-categorizer returns 404 when ADMIN_ENABLED is false (the default)."""
    from app import config

    monkeypatch.setenv("ADMIN_ENABLED", "false")
    config.get_settings.cache_clear()

    resp = client.post("/ml/train-categorizer")
    assert resp.status_code == 404

    config.get_settings.cache_clear()


def test_train_categorizer_accessible_when_admin_enabled(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /ml/train-categorizer returns 200 when ADMIN_ENABLED is true."""
    from app import config

    monkeypatch.setenv("ADMIN_ENABLED", "true")
    config.get_settings.cache_clear()

    resp = client.post("/ml/train-categorizer")
    assert resp.status_code == 200

    config.get_settings.cache_clear()
