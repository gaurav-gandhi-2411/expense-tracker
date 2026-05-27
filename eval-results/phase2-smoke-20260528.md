# Phase 2 ML Endpoint Smoke Test — 2026-05-28

Server: uvicorn app.main:app --host 127.0.0.1 --port 8000
DB: expense_tracker.db (26 seeded expenses)

---

## 1. POST /ml/categorize

**Request:**
```json
POST /ml/categorize
Content-Type: application/json

{"text": "swiggy order 480"}
```

**Response (200 OK):**
```json
{"category":"utilities","score":0.18866586685180664,"mode":"zero-shot"}
```

**Observation:** Categorized as "utilities" (score 0.19). Expected category would be "food" or "food-delivery". Low confidence score (0.19) — "swiggy" is a food delivery brand not in the prototype vocabulary.

---

## 2. GET /ml/anomalies?since=2026-01-01

**Request:**
```
GET /ml/anomalies?since=2026-01-01
```

**Response (200 OK):**
```json
[
  {"expense_id":25,"amount":16363.64,"category":"rent","reason":"rare category in your history (rent)","score":0.6892914893031834},
  {"expense_id":26,"amount":1200.0,"category":"food","reason":"2.4x your typical food spend","score":0.5836272992033978},
  {"expense_id":5,"amount":1880.1,"category":"utilities","reason":"rare category in your history (utilities)","score":0.583530428384442},
  {"expense_id":15,"amount":1486.38,"category":"groceries","reason":"unusual groceries expense","score":0.5514482258433816},
  {"expense_id":7,"amount":1468.23,"category":"entertainment","reason":"1.8x your typical entertainment spend","score":0.5449983377241036},
  {"expense_id":1,"amount":637.57,"category":"groceries","reason":"unusual groceries expense","score":0.5332935129183525},
  {"expense_id":9,"amount":434.89,"category":"transport","reason":"unusual transport expense","score":0.5256522497627185},
  {"expense_id":23,"amount":386.16,"category":"transport","reason":"unusual transport expense","score":0.520856321744338},
  {"expense_id":18,"amount":548.06,"category":"groceries","reason":"unusual groceries expense","score":0.5135773309119764},
  {"expense_id":21,"amount":457.17,"category":"entertainment","reason":"unusual entertainment expense","score":0.5123961652605428},
  {"expense_id":6,"amount":1351.09,"category":"groceries","reason":"unusual groceries expense","score":0.5062517096283374}
]
```

**Observation:** 11 of 26 expenses flagged (42%). High flag rate on seeded deterministic data — IsolationForest contamination parameter may be generous. Reasons are human-readable and category-aware.

---

## 3. GET /ml/forecast?horizon=2

**Request:**
```
GET /ml/forecast?horizon=2
```

**Response (200 OK):**
```json
{
  "horizon_months": 2,
  "points": [
    {"month":"2026-06","predicted":24381.83792706138,"lower":18773.868774188493,"upper":30421.515952326074},
    {"month":"2026-07","predicted":30548.412810562266,"lower":24552.287000687047,"upper":36130.13633436821}
  ],
  "mode": "prophet",
  "note": "Prophet forecast based on 4 months of history."
}
```

**Observation:** Prophet ran in full mode (not low-confidence-average fallback) on 4 months of history. Upward trend in predictions may reflect seasonal pattern in seeded data. Confidence intervals are reasonable width (~±6k).

---

## 4. POST /ml/train-categorizer

**Request:**
```
POST /ml/train-categorizer
```

**Response (200 OK):**
```json
{"status":"refused-insufficient-data","reason":"need >= 30 examples in at least 2 categories; 'utilities' has only 1.","n_examples":26,"n_categories":6,"metrics":null}
```

**Observation:** Correctly refused training. Threshold logic works — reports specific blocking reason (utilities has only 1 example). n_examples=26 matches DB row count. Will auto-train once data accumulates past threshold.

---

## Summary

| Endpoint | Status | Notes |
|---|---|---|
| POST /ml/categorize | 200 OK | Wrong category for "swiggy order 480" (got utilities, expected food) |
| GET /ml/anomalies | 200 OK | 11/26 flagged; high rate on seeded data |
| GET /ml/forecast | 200 OK | Prophet mode, 4 months history, upward trend |
| POST /ml/train-categorizer | 200 OK | Correctly refused (26 < 30 threshold) |
