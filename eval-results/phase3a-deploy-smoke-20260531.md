# Phase 3a Deploy Smoke Test — 2026-05-31

## Deployment

| Field | Value |
|---|---|
| Cloud Run service | expense-tracker |
| Revision | expense-tracker-00001-98w |
| Region | us-central1 |
| Project | expense-tracker-498014 |
| Service URL | https://expense-tracker-242393598566.us-central1.run.app |
| Deploy time | 2026-05-31 |

---

## Smoke test 1 — GET /health

**Request**
```
GET https://expense-tracker-242393598566.us-central1.run.app/health
```

**Response**
```
HTTP 200 OK  (elapsed: 1s — container warm from deploy)

{
  "status": "ok"
}
```

**Result: PASS** — health endpoint returned 200 with expected body.

---

## Smoke test 2 — GET /expenses (no auth)

**Request**
```
GET https://expense-tracker-242393598566.us-central1.run.app/expenses
(no Authorization header)
```

**Response**
```
HTTP 401 Unauthorized  (elapsed: 1s)

{
  "detail": "Missing authentication token"
}
```

**Result: PASS** — unauthenticated request correctly rejected with 401 and expected detail message.

---

## Summary

| Check | Expected | Got | Status |
|---|---|---|---|
| GET /health | 200 `{"status":"ok"}` | 200 `{"status":"ok"}` | PASS |
| GET /expenses (no auth) | 401 | 401 `{"detail":"Missing authentication token"}` | PASS |

Cold-start note: container was still warm from the just-completed deploy. First truly cold start (after idle period) will take 60–120s due to sentence-transformers + torch model load.
