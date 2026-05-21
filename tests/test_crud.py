from __future__ import annotations

from fastapi.testclient import TestClient

_VALID_PAYLOAD = {
    "amount": 50.0,
    "category": "food",
    "description": "lunch",
    "occurred_at": "2026-01-15",
}


def _create(client: TestClient, payload: dict | None = None) -> dict:
    """POST one expense and return response JSON."""
    return client.post("/expenses", json=payload or _VALID_PAYLOAD).json()


def test_create_expense_returns_201_and_payload(client: TestClient) -> None:
    r = client.post("/expenses", json=_VALID_PAYLOAD)
    assert r.status_code == 201
    body = r.json()
    assert isinstance(body["id"], int)
    assert isinstance(body["created_at"], str)  # ISO datetime string
    assert body["amount"] == 50.0
    assert body["category"] == "food"
    assert body["description"] == "lunch"
    assert body["occurred_at"] == "2026-01-15"


def test_get_expense_by_id_returns_row(client: TestClient) -> None:
    created = _create(client)
    r = client.get(f"/expenses/{created['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]
    assert r.json()["amount"] == created["amount"]


def test_get_expense_by_id_returns_404_when_missing(client: TestClient) -> None:
    r = client.get("/expenses/99999")
    assert r.status_code == 404


def test_list_expenses_returns_all(client: TestClient) -> None:
    _create(client, {**_VALID_PAYLOAD, "description": "first"})
    _create(client, {**_VALID_PAYLOAD, "description": "second"})
    r = client.get("/expenses")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_patch_expense_partial_update(client: TestClient) -> None:
    created = _create(client)
    r = client.patch(f"/expenses/{created['id']}", json={"amount": 99.0})
    assert r.status_code == 200
    body = r.json()
    assert body["amount"] == 99.0
    # unchanged fields survive the partial update
    assert body["category"] == created["category"]
    assert body["description"] == created["description"]
    assert body["occurred_at"] == created["occurred_at"]


def test_patch_expense_returns_404_when_missing(client: TestClient) -> None:
    r = client.patch("/expenses/99999", json={"amount": 10.0})
    assert r.status_code == 404


def test_delete_expense_returns_204_and_then_404(client: TestClient) -> None:
    created = _create(client)
    expense_id = created["id"]
    r = client.delete(f"/expenses/{expense_id}")
    assert r.status_code == 204
    r2 = client.get(f"/expenses/{expense_id}")
    assert r2.status_code == 404


def test_delete_returns_404_when_missing(client: TestClient) -> None:
    r = client.delete("/expenses/99999")
    assert r.status_code == 404
