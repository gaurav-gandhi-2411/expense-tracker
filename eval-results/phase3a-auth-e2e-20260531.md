# Phase 3a Authenticated E2E Smoke Test — 2026-05-31

## Deployment

| Field | Value |
|---|---|
| Cloud Run service | expense-tracker |
| Revision | expense-tracker-00003-xw2 |
| Region | us-central1 |
| Project | expense-tracker-498014 |
| Service URL | https://expense-tracker-242393598566.us-central1.run.app |
| Test user ID | f5413748-d6a7-49ef-ad1a-3b0a37bbe6e6 |
| Auth algorithm | ES256 (Supabase asymmetric JWT, PyJWKClient) |

---

## Step 3c — Mint JWT (Supabase password grant)

**Request**
```
POST https://ckedawgfjwzefayhcybe.supabase.co/auth/v1/token?grant_type=password
Headers: apikey: <REDACTED>, Content-Type: application/json
Body: {"email": "test@expense-tracker.local", "password": "<REDACTED>"}
```

**Result:** access_token received (ES256, kid=613ebcb8-554b-49f8-8f53-77feddadd514).
JWT used in all subsequent requests as `Authorization: Bearer <REDACTED>`.

---

## Step 3d — GET /expenses (authenticated, new user)

**Request**
```
GET https://expense-tracker-242393598566.us-central1.run.app/expenses
Authorization: Bearer <REDACTED>
```

**Response**
```
HTTP 200 OK  (3844ms — cold start + JWKS fetch on first request)

[]
```

**Result: PASS** — authenticated request accepted; empty list correct for new user.

---

## Step 3e — POST /expenses/from-text

**Request**
```
POST https://expense-tracker-242393598566.us-central1.run.app/expenses/from-text
Authorization: Bearer <REDACTED>
Content-Type: application/json

{"text": "coffee 180"}
```

**Response**
```
HTTP 200 OK  (3699ms)

{
  "amount": 180.0,
  "category": "food",
  "description": "coffee",
  "occurred_at": "2026-05-31",
  "id": 1,
  "created_at": "2026-05-31T15:49:58.515476"
}
```

**Result: PASS** — LLM parsed "coffee 180" → amount=180, category=food, description=coffee.
`user_id` is not in the response (correct — internal field); row was saved to Supabase Postgres.

---

## Step 3f — GET /expenses (verify persistence)

**Request**
```
GET https://expense-tracker-242393598566.us-central1.run.app/expenses
Authorization: Bearer <REDACTED>
```

**Response**
```
HTTP 200 OK  (1663ms)

[
  {
    "amount": 180.0,
    "category": "food",
    "description": "coffee",
    "occurred_at": "2026-05-31",
    "id": 1,
    "created_at": "2026-05-31T15:49:58.515476"
  }
]
```

**Result: PASS** — expense persists across requests; user_id scoping returns exactly 1 row.

---

## Summary

| Step | Check | Expected | Got | Status |
|---|---|---|---|---|
| 3c | Mint JWT | ES256 token issued | ES256 token, user_id confirmed | PASS |
| 3d | GET /expenses (auth) | 200, [] | 200, [] | PASS |
| 3e | POST /expenses/from-text | 200, parsed expense | 200, amount=180 category=food | PASS |
| 3f | GET /expenses (verify) | 200, 1 item | 200, count=1, row matches 3e | PASS |

---

## Issues encountered and resolved

| Issue | Root cause | Fix |
|---|---|---|
| 401 on initial deploy | `app/auth.py` only accepted HS256; Supabase newer projects issue ES256 | Updated auth.py to dual-algorithm (HS256 + ES256 via PyJWKClient) |
| 401 after ES256 code added | `jwt.decode` missing `audience="authenticated"` — Supabase tokens carry `aud` claim | Added `audience="authenticated"` to both decode paths |

Both fixes are in `app/auth.py` (commit `fed4edf`), covered by updated `tests/test_auth.py`.
