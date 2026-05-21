from __future__ import annotations

from fastapi.testclient import TestClient


def test_stats_by_month_groups_and_sorts_asc(client: TestClient) -> None:
    # Jan: 40 + 60 = 100; Feb: 150
    client.post("/expenses", json={
        "amount": 40.0, "category": "food", "description": "", "occurred_at": "2026-01-10",
    })
    client.post("/expenses", json={
        "amount": 60.0, "category": "food", "description": "", "occurred_at": "2026-01-20",
    })
    client.post("/expenses", json={
        "amount": 150.0, "category": "food", "description": "", "occurred_at": "2026-02-05",
    })

    r = client.get("/stats/by-month")
    assert r.status_code == 200
    results = r.json()
    assert len(results) == 2
    assert results[0]["month"] == "2026-01"
    assert results[0]["total"] == 100.0
    assert results[1]["month"] == "2026-02"
    assert results[1]["total"] == 150.0


def test_stats_by_month_empty_when_no_expenses(client: TestClient) -> None:
    r = client.get("/stats/by-month")
    assert r.status_code == 200
    assert r.json() == []


def test_stats_by_category_groups_and_sorts_total_desc(client: TestClient) -> None:
    # food total: 200; transport total: 80 — food comes first (DESC)
    client.post("/expenses", json={
        "amount": 120.0, "category": "food", "description": "", "occurred_at": "2026-01-10",
    })
    client.post("/expenses", json={
        "amount": 80.0, "category": "food", "description": "", "occurred_at": "2026-01-15",
    })
    client.post("/expenses", json={
        "amount": 80.0, "category": "transport", "description": "", "occurred_at": "2026-01-20",
    })

    r = client.get("/stats/by-category")
    assert r.status_code == 200
    results = r.json()
    assert len(results) == 2
    assert results[0]["category"] == "food"
    assert results[0]["total"] == 200.0
    assert results[1]["category"] == "transport"
    assert results[1]["total"] == 80.0


def test_stats_by_category_empty_when_no_expenses(client: TestClient) -> None:
    r = client.get("/stats/by-category")
    assert r.status_code == 200
    assert r.json() == []
