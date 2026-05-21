from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_filtered_by_category(client: TestClient) -> None:
    client.post("/expenses", json={
        "amount": 10.0, "category": "food", "description": "", "occurred_at": "2026-01-10",
    })
    client.post("/expenses", json={
        "amount": 20.0, "category": "transport", "description": "", "occurred_at": "2026-01-10",
    })

    r = client.get("/expenses?category=food")
    assert r.status_code == 200
    results = r.json()
    assert len(results) == 1
    assert results[0]["category"] == "food"


def test_list_filtered_by_since(client: TestClient) -> None:
    client.post("/expenses", json={
        "amount": 10.0, "category": "food", "description": "", "occurred_at": "2026-01-15",
    })
    client.post("/expenses", json={
        "amount": 20.0, "category": "food", "description": "", "occurred_at": "2026-02-10",
    })

    r = client.get("/expenses?since=2026-02-01")
    assert r.status_code == 200
    results = r.json()
    assert len(results) == 1
    assert results[0]["occurred_at"] == "2026-02-10"


def test_list_filtered_by_category_and_since_combined(client: TestClient) -> None:
    # food/Jan — excluded by since filter
    client.post("/expenses", json={
        "amount": 10.0, "category": "food", "description": "", "occurred_at": "2026-01-20",
    })
    # food/Feb — matches both filters
    client.post("/expenses", json={
        "amount": 30.0, "category": "food", "description": "", "occurred_at": "2026-02-05",
    })
    # transport/Feb — excluded by category filter
    client.post("/expenses", json={
        "amount": 50.0, "category": "transport", "description": "", "occurred_at": "2026-02-10",
    })

    r = client.get("/expenses?category=food&since=2026-02-01")
    assert r.status_code == 200
    results = r.json()
    assert len(results) == 1
    assert results[0]["category"] == "food"
    assert results[0]["occurred_at"] == "2026-02-05"


def test_list_with_no_filters_returns_all(client: TestClient) -> None:
    client.post("/expenses", json={
        "amount": 10.0, "category": "food", "description": "", "occurred_at": "2026-01-01",
    })
    client.post("/expenses", json={
        "amount": 20.0, "category": "transport", "description": "", "occurred_at": "2026-02-01",
    })
    client.post("/expenses", json={
        "amount": 30.0, "category": "utilities", "description": "", "occurred_at": "2026-03-01",
    })

    r = client.get("/expenses")
    assert r.status_code == 200
    assert len(r.json()) == 3
