# Current State: expense-tracker (post-Phase 3a)

## Project goal
A personal expense tracker as a FastAPI service. Multi-user via Supabase Auth (JWT), per-user data isolation, Alembic migrations, Supabase Postgres in prod / SQLite in local dev. Backend is live on GCP Cloud Run. Phase 3b: Next.js 15 frontend on Vercel.

## Live deployment

| Field | Value |
|---|---|
| Service URL | https://expense-tracker-242393598566.us-central1.run.app |
| Cloud Run service | expense-tracker |
| Region | us-central1 |
| GCP project | expense-tracker-498014 |
| Deploy date | 2026-05-31 |

First request after idle: 60–120s cold start (sentence-transformers + torch load). Subsequent requests: normal latency.

## Directory structure (key files only)
```
expense-tracker/
├── pyproject.toml          # deps: fastapi, sqlalchemy 2.x sync, pydantic v2, uvicorn, pytest,
│                           #       httpx, ruff, mypy, groq, pydantic-settings, python-dotenv,
│                           #       pytest-mock, sentence-transformers, scikit-learn, prophet, joblib,
│                           #       pyjwt[crypto], psycopg2-binary, alembic
├── README.md               # install / run / seed / curl + ML features + Production setup
├── spec.md                 # Phase 3b spec (active)
├── CURRENT_STATE.md        # this file
├── Dockerfile              # CPU-only torch (~200 MB vs 2 GB CUDA), multi-dep build
├── .dockerignore           # excludes .venv/, tests/, eval-results/, models/, .env*, .git/
├── alembic.ini             # Alembic config pointing at migrations/
├── .env                    # gitignored — all secrets live here
├── .env.example            # committed template with all 9 env vars
├── eval-results/           # committed — eval + smoke artifacts
│   ├── phase2-eval-20260528.txt
│   ├── phase2-smoke-20260528.md
│   ├── phase2-eval-v2-20260528.txt
│   ├── phase2-smoke-v2-20260528.md
│   └── phase3a-deploy-smoke-20260531.md   # Phase 3a smoke (all 4 steps PASS)
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 001_baseline_schema.py   # creates expenses table from scratch
│       └── 002_add_user_id.py       # adds user_id column + index
├── app/
│   ├── main.py             # FastAPI app + ALL 16 routes + CORS middleware + logging config
│   ├── auth.py             # Supabase JWT validation — dual-algorithm (HS256 + ES256/JWKS)
│   ├── db.py               # DATABASE_URL env; NullPool for Postgres; SQLite default  [LOAD-BEARING]
│   ├── models.py           # Expense ORM model + user_id column                       [LOAD-BEARING]
│   ├── schemas.py          # Pydantic v2 schemas
│   ├── stats.py            # /stats/by-month + /stats/by-category (user-scoped)
│   ├── config.py           # pydantic-settings Settings — all 9 env vars              [LOAD-BEARING]
│   ├── llm.py              # Groq client wrapper (unchanged)                           [LOAD-BEARING]
│   ├── parser.py           # parse_expense_text()                                      [Phase 1]
│   ├── insights.py         # monthly + category narrative (user-scoped)               [Phase 1]
│   └── ml/
│       ├── __init__.py
│       ├── embeddings.py   # sentence-transformers loader                              [LOAD-BEARING]
│       ├── categorizer.py  # zero-shot + logistic-regression trainer                  [LOAD-BEARING]
│       ├── anomaly.py      # IsolationForest (user-scoped)                            [LOAD-BEARING]
│       └── forecast.py     # Prophet (user-scoped)                                    [LOAD-BEARING]
├── scripts/
│   ├── seed.py             # 25 deterministic expenses; --user-id UUID arg
│   ├── deploy.sh           # bash deploy script (reference)
│   ├── deploy.ps1          # PowerShell deploy script (Windows)
│   ├── eval_parser.py      # manual parser eval (not in CI)
│   └── eval_ml.py          # manual ML eval harness (not in CI)
└── tests/                  # 141/141 pass
    ├── conftest.py         # in-memory SQLite + auth dep override              [LOAD-BEARING]
    ├── test_auth.py        # JWT validation: valid/missing/invalid/expired
    ├── test_isolation.py   # user A cannot access user B data (all 16 endpoints)
    ├── test_admin_gate.py  # POST /ml/train-categorizer gated behind ADMIN_ENABLED
    ├── test_migrations.py  # alembic upgrade head produces expected schema
    ├── test_crud.py
    ├── test_filters.py
    ├── test_health.py
    ├── test_stats.py
    ├── test_llm.py
    ├── test_llm_endpoints.py
    ├── test_insights.py
    ├── test_parser.py
    ├── test_embeddings.py
    ├── test_categorizer.py
    ├── test_anomaly.py
    ├── test_forecast.py
    └── test_ml_endpoints.py
```

## Endpoints (16 total)

**v0 (8):** GET /health, POST /expenses, GET /expenses, GET /expenses/{id}, PATCH /expenses/{id}, DELETE /expenses/{id}, GET /stats/by-month, GET /stats/by-category

**Phase 1 (4):** POST /expenses/parse, POST /expenses/from-text, GET /insights/monthly, GET /insights/category

**Phase 2 (4):** POST /ml/categorize, POST /ml/train-categorizer, GET /ml/anomalies, GET /ml/forecast

All endpoints except `GET /health` require a valid Supabase JWT in the `Authorization: Bearer <token>` header.

## Auth model

- **Provider:** Supabase Auth (JWT)
- **Algorithms:** Dual — HS256 (legacy/local) and ES256 (Supabase asymmetric, production default)
- **ES256 path:** `app/auth.py` fetches JWKS from `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` via `PyJWKClient` (cached, 1-hour lifespan). Signing key resolved per-request from JWT header.
- **HS256 path:** symmetric verify using `SUPABASE_JWT_SECRET` env var (kept for backwards compat with test tokens)
- **Both algorithms:** require `audience="authenticated"` claim and `["sub", "exp"]` fields
- **Validation:** `get_current_user_id()` FastAPI dependency; reads `alg` from unverified header to select path; extracts `sub` as `user_id` (UUID string)
- **Enforcement:** all 15 non-health endpoints inject `get_current_user_id` as a dependency
- **Data isolation:** every DB query filters `WHERE user_id = :current_user_id`; cross-user access returns 404 (not 403)
- **Admin gate:** `POST /ml/train-categorizer` additionally requires `ADMIN_ENABLED=true` env var; returns 404 when false

## Environment variables

All 9 env vars are required in production (set as Cloud Run env vars via deploy script):

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | Supabase session-pooler URL (`postgresql+psycopg2://...`) | `sqlite:///./expense_tracker.db` |
| `SUPABASE_JWT_SECRET` | Supabase project JWT secret (HS256 path) | — |
| `SUPABASE_URL` | Supabase project URL (`https://xxxx.supabase.co`) | — |
| `GROQ_API_KEY` | Groq API key for LLM features | — |
| `RUN_MIGRATIONS_ON_STARTUP` | Run `alembic upgrade head` at app startup | `false` |
| `ADMIN_ENABLED` | Enable POST /ml/train-categorizer | `false` |
| `CORS_ALLOWED_ORIGINS` | Comma-separated allowed origins | `""` |
| `GROQ_MODEL` | Primary LLM model | `llama-3.3-70b-versatile` |
| `GROQ_FALLBACK_MODEL` | Fallback LLM model | `llama-3.1-8b-instant` |

## Load-bearing files (touch with care)
- **app/db.py** — `get_db` DI hook overridden in tests. Don't change signature.
- **app/models.py** — `Expense` ORM model. Adding columns fine; changing/removing breaks stored data.
- **tests/conftest.py** — in-memory SQLite + per-test rollback + auth dep override. Adding fixtures fine; don't modify the `client` fixture.
- **app/llm.py** — Groq client. Don't change public surface.
- **app/config.py** — Settings is `@lru_cache`d. All config flows through it.
- **app/auth.py** — JWT dual-algorithm validator. If `SUPABASE_JWT_SECRET` is wrong (HS256) or JWKS is unreachable (ES256), authenticated endpoints return 401.

## Test / lint / types state
- `pytest -v` → 141/141 pass
- `ruff check .` → clean
- `mypy app` → clean (strict=false)
- Coverage: per-feature test presence (no threshold configured)

## Alembic migrations
- `001_baseline_schema.py` — creates `expenses` table (for fresh prod DB)
- `002_add_user_id.py` — adds `user_id` column + index
- `RUN_MIGRATIONS_ON_STARTUP=true` triggers `alembic upgrade head` at app boot (set in Cloud Run env vars)
- Run locally: `alembic upgrade head` (uses `DATABASE_URL` from `.env`)

## Conventions in use
- `from __future__ import annotations` at top of every Python file
- Type hints on every function; docstrings on non-trivial ones
- Pydantic v2 (`ConfigDict`, not nested `Config`)
- SQLAlchemy 2.x style (`Mapped[T]`, `mapped_column`, `select(...)`)
- Conventional commits; one concept per commit
- Single-currency (rupees)
- LLM never called from tests — always mocked
- ML models never loaded in tests — mocked via pytest-mock

## Phase plan

| Phase | Status | Summary |
|---|---|---|
| v0 | Done | CRUD + stats, 8 endpoints, SQLite |
| Phase 1 | Done | LLM parse + from-text + insights, 4 endpoints, Groq |
| Phase 2 | Done | Local ML: categorizer + anomaly + forecast + train, 4 endpoints |
| Phase 2.5 | Done | Validation + cleanup: eval artifacts, pytest warning, CURRENT_STATE refresh |
| Phase 2.6 | Done | ML quality: brand-keyword prototypes, LLM fallback, anomaly tuning. Categorizer 8/8. |
| Phase 3a | Done | Production backend: dual-algo JWT auth (HS256+ES256), multi-user isolation, Alembic, Postgres, Cloud Run deploy |
| Phase 3b | Active | Next.js 16 frontend on Vercel — sign-in/up, expense CRUD, NL input hero |
| Phase 3b.1 | Done | Auth hardening + E2E tests — 4 auth bugs fixed, 9 Playwright scenarios green |

## Phase 3b plan

**Goal:** User-facing web frontend on Vercel, connected to the live Cloud Run backend. Usable by a friend with a sign-up link.

**Stack:**
- Next.js 16 (App Router only) + TypeScript strict + Tailwind CSS v4
- shadcn/ui for all UI primitives; lucide-react for icons
- @supabase/supabase-js + @supabase/ssr for auth (SSR-safe cookies)
- TanStack Query v5 for server state (object-form API)
- react-hook-form + zod for form validation
- date-fns for date formatting

**Frontend lives at:** `frontend/` (repo root sibling to `app/`)

**5 pages:**
1. `/` — root redirect (→ /expenses if authed, → /sign-in if not)
2. `/sign-in` — email/password login via Supabase Auth
3. `/sign-up` — registration via Supabase Auth
4. `/expenses` — list view (desktop table + mobile cards)
5. `/expenses/new` — NL input hero + manual form secondary
6. `/expenses/[id]/edit` — pre-filled form with save/delete

**Backend change:** CORS_ALLOWED_ORIGINS env var update only (via `gcloud run services update`), no code changes.

**Out of scope for 3b:** insights view, stats charts, ML demo UIs, component/E2E tests, dark mode, password reset, social auth, pagination, CSV export.

## Phase 3c plan (next after 3b)

- Insights view (monthly + category narratives from /insights/* endpoints)
- Stats charts: by-month and by-category visualizations (recharts)
- ML feature demo UIs: categorize tester, anomalies view, forecast view
- Component tests (Vitest + React Testing Library)
- E2E tests (Playwright)
- CI for the frontend (GitHub Actions)

## Known issues / accepted debt
- No pagination on list endpoint — fine for personal scale.
- No LLM response caching — each parse/insight is a fresh Groq call.
- Groq free-tier rate limits (~30 rpm on 70B) — fine for personal use.
- `min_anomaly_samples=50`: seed.py (25 rows) falls below threshold; anomaly eval skipped by design. Run seed twice or use unit tests.
- CORS_ALLOWED_ORIGINS is empty in current Cloud Run deploy — will be updated at Phase 3b Checkpoint E once Vercel URL is known.
- Cold start 60–120s: expected on min-instances=0 free tier. Not a bug.
- Preview Vercel deploys will not be CORS-permitted in 3b (only production URL + localhost hardcoded). Acceptable; revisit in 3c.
