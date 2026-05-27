# Phase 2.6 live smoke test — 2026-05-28

Server: FastAPI TestClient (in-process) — chosen over uvicorn background process due to
Windows cp1252/PowerShell redirect fragility encountered during this session. Per spec
escalation note, TestClient is an acceptable alternative; noted here for orchestrator
verification.

DB: expense_tracker.db (26 seeded expenses)

---

## Input 1: "swiggy order 480"

**Request:**
```json
POST /ml/categorize
Content-Type: application/json

{"text": "swiggy order 480"}
```

**Response (200 OK):**
```json
{
  "category": "food",
  "score": 0.3814724087715149,
  "mode": "zero-shot",
  "confidence_note": null
}
```

**Interpretation:** Zero-shot path fired. Score 0.38 — above the 0.30 LLM-fallback
threshold. The expanded "swiggy zomato dunzo …" prototype text moved "swiggy order" into
the food cluster without needing an LLM call. Category: food (correct).

---

## Input 2: "uber to office 240"

**Request:**
```json
POST /ml/categorize
Content-Type: application/json

{"text": "uber to office 240"}
```

**Response (200 OK):**
```json
{
  "category": "transport",
  "score": 0.3803568184375763,
  "mode": "zero-shot",
  "confidence_note": null
}
```

**Interpretation:** Zero-shot path fired. Score 0.38 — the "ola uber rapido auto taxi …"
prototype text correctly anchored "uber to office" in the transport cluster.
Category: transport (correct, was rent@0.23 in v1).

---

## Input 3: "netflix 649"

**Request:**
```json
POST /ml/categorize
Content-Type: application/json

{"text": "netflix 649"}
```

**Response (200 OK):**
```json
{
  "category": "entertainment",
  "score": 0.38382139801979065,
  "mode": "zero-shot",
  "confidence_note": null
}
```

**Interpretation:** Zero-shot path fired. Score 0.38 — "netflix prime hotstar spotify
movies concert streaming" prototype absorbed "netflix" into the entertainment cluster.
Removing "subscription" as a competing prototype (Steps 1-4) helped; even without that,
the richer entertainment prototype text is the primary driver.
Category: entertainment (correct, was subscription@0.31 in v1).

---

## Before/After comparison — Phase 2.5 (v1) vs Phase 2.6 (v2)

| Input | v1 category | v1 score | v1 mode | v2 category | v2 score | v2 mode | Status |
|-------|-------------|----------|---------|-------------|----------|---------|--------|
| swiggy order 480 | utilities | 0.19 | zero-shot | food | 0.38 | zero-shot | improved |
| uber to office 240 | rent | 0.23 | zero-shot | transport | 0.38 | zero-shot | improved |
| netflix 649 | subscription | 0.31 | zero-shot | entertainment | 0.38 | zero-shot | improved |

---

## Design intent assessment

All three cases improved from wrong to correct via zero-shot alone, with scores
clustering tightly at 0.38. The expanded Indian brand keyword prototypes were
sufficient to move swiggy, uber, and netflix into their correct clusters without
requiring LLM fallback for any of these inputs.

The LLM fallback path (threshold < 0.30) was NOT triggered for any smoke case —
this is the desired outcome. The fallback exists as a safety net for genuinely
ambiguous inputs; for common Indian app brand names, zero-shot with richer
prototypes is the right first-pass solution.

The anomaly section now skips on 26 rows (threshold raised to 50 in Step 3), which
is expected and noted in the eval artifact.
