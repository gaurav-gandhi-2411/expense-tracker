# Current State: expense-tracker (post-Phase 3b.1)

## Project goal
A personal expense tracker — FastAPI backend, Next.js frontend. Multi-user via Supabase Auth (JWT), per-user data isolation, Alembic migrations, Supabase Postgres in prod / SQLite in local dev. Backend live on GCP Cloud Run; frontend live on Vercel. Phase 4 adds household/group shared-expense flows.

## Live deployment

**Backend (Cloud Run)**

| Field | Value |
|---|---|
| Service URL | https://expense-tracker-242393598566.us-central1.run.app |
| Cloud Run service | expense-tracker |
| Region | us-central1 |
| GCP project | expense-tracker-498014 |
| Deploy date | 2026-05-31 |

First request after idle: 60–120s cold start (sentence-transformers + torch load). Subsequent requests: normal latency.

**Frontend (Vercel)**

| Field | Value |
|---|---|
| Production URL | https://expense-tracker-tawny-eight-98.vercel.app |
| Framework | Next.js 16.2.6 (App Router) |
| Deploy date | Phase 3b / 2026-06-01 |

## Directory structure (key files only)
```
expense-tracker/
├── pyproject.toml          # deps: fastapi, sqlalchemy 2.x sync, pydantic v2, uvicorn, pytest,
│                           #       httpx, ruff, mypy, groq, pydantic-settings, python-dotenv,
│                           #       pytest-mock, sentence-transformers, scikit-learn, prophet, joblib,
│                           #       pyjwt[crypto], psycopg2-binary, alembic
├── README.md               # install / run / seed / curl + ML features + Production setup
├── spec.md                 # Phase 3b spec (reference — phase complete)
├── CURRENT_STATE.md        # this file
├── Dockerfile              # CPU-only torch (~200 MB vs 2 GB CUDA), multi-dep build
├── .dockerignore           # excludes .venv/, tests/, eval-results/, models/, .env*, .git/
├── alembic.ini             # Alembic config pointing at migrations/
├── .env                    # gitignored — all secrets live here
├── .env.example            # committed template with all 9 env vars
├── eval-results/           # committed — eval + smoke artifacts
│   ├── phase2-smoke-20260528.md
│   ├── phase2-smoke-v2-20260528.md
│   ├── phase3a-deploy-smoke-20260531.md   # Phase 3a smoke (4/4 PASS)
│   ├── phase3a-auth-e2e-20260531.md       # Phase 3a authenticated E2E (4/4 PASS)
│   └── phase3b1-auth-fix-20260601.md      # Phase 3b.1 auth fix log + 9/9 E2E PASS
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
│   ├── llm.py              # Groq client wrapper                                       [LOAD-BEARING]
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
├── tests/                  # 143/143 pass
│   ├── conftest.py         # in-memory SQLite + auth dep override              [LOAD-BEARING]
│   ├── test_auth.py
│   ├── test_isolation.py
│   ├── test_admin_gate.py
│   ├── test_migrations.py
│   ├── test_crud.py
│   ├── test_filters.py
│   ├── test_health.py
│   ├── test_stats.py
│   ├── test_llm.py
│   ├── test_llm_endpoints.py
│   ├── test_insights.py
│   ├── test_parser.py
│   ├── test_embeddings.py
│   ├── test_categorizer.py
│   ├── test_anomaly.py
│   ├── test_forecast.py
│   └── test_ml_endpoints.py
└── frontend/               # Next.js 16 — deployed to Vercel
    ├── package.json        # next 16.2.6, react 19, tailwindcss v4, @base-ui/react,
    │                       # @supabase/ssr, @tanstack/react-query v5, react-hook-form, zod
    ├── next.config.ts
    ├── proxy.ts            # Supabase SSR cookie refresh + auth redirects (NOT middleware.ts)
    ├── playwright.config.ts
    ├── tsconfig.json
    ├── components.json     # shadcn/ui config (base-ui adapter)
    ├── .env.local          # gitignored — NEXT_PUBLIC_* vars for local dev
    ├── .env.local.example
    ├── .env.test.local     # gitignored — TEST_USER_EMAIL + TEST_USER_PASSWORD for Playwright
    ├── .env.test.local.example
    ├── e2e/
    │   └── auth.spec.ts    # 9 Playwright auth scenarios (all PASS on Chromium)
    ├── public/
    └── src/
        ├── app/
        │   ├── layout.tsx                          # root layout + providers
        │   ├── page.tsx                            # root redirect (→ /expenses or /sign-in)
        │   ├── globals.css
        │   ├── sign-in/
        │   │   ├── layout.tsx                      # server guard: authenticated → /expenses
        │   │   └── page.tsx
        │   ├── sign-up/
        │   │   └── page.tsx
        │   └── (authenticated)/                    # route group — auth-gated
        │       ├── layout.tsx                      # server guard: unauthenticated → /sign-in
        │       ├── expenses/
        │       │   ├── page.tsx                    # list view (desktop table + mobile cards)
        │       │   ├── new/page.tsx                # NL input hero + manual form
        │       │   └── [id]/
        │       │       ├── edit/page.tsx
        │       │       └── edit-client.tsx         # pre-filled form with save/delete
        ├── components/
        │   ├── nav.tsx
        │   ├── expense-card-mobile.tsx
        │   ├── expense-form.tsx
        │   ├── nl-input.tsx
        │   ├── providers.tsx                       # QueryClientProvider + Toaster
        │   └── ui/                                 # shadcn primitives (button, card, dialog, …)
        ├── lib/
        │   ├── api.ts                              # fetch wrapper calling Cloud Run via proxy
        │   ├── utils.ts
        │   ├── hooks/
        │   │   ├── use-expenses.ts                 # TanStack Query hooks
        │   │   └── use-user.ts
        │   └── supabase/
        │       ├── client.ts                       # browser Supabase client
        │       └── server.ts                       # server Supabase client (cookie-based)
        └── types/
            └── expense.ts
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

## Supabase config

| Setting | Value |
|---|---|
| Email confirmation | OFF (Option A — users land in app immediately after sign-up) |
| Site URL | `https://expense-tracker-tawny-eight-98.vercel.app` |
| CORS_ALLOWED_ORIGINS (Cloud Run) | Vercel prod URL + `http://localhost:3000` |

## Frontend stack

- **Next.js 16.2.6** — App Router only; no Pages Router
- **proxy.ts** (not `middleware.ts`) — handles Supabase SSR cookie refresh and auth redirects. Redirects must propagate `supabaseResponse.cookies` or token rotation silently breaks sessions.
- **TypeScript strict**, Tailwind CSS v4
- **shadcn/ui** built on **@base-ui/react** (not Radix UI). `DropdownMenuItem` uses `onClick`, not `onSelect` (Radix convention — silent no-op on base-ui).
- **TanStack Query v5** (object-form API — `queryKey`/`queryFn` in a single object arg)
- **@supabase/ssr** for SSR-safe cookie-based auth; `createServerClient` in server components, `createBrowserClient` in client components
- **react-hook-form + zod** for form validation
- **Auth transitions use `window.location.href`** (full HTTP navigation through proxy.ts), not `router.push` — ensures cookie refresh pipeline runs on the next request

## Vercel environment variables

All three required at build time and runtime:

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key |
| `NEXT_PUBLIC_API_BASE_URL` | Cloud Run service URL (no trailing slash) |

## Backend environment variables

All 9 env vars required in production (set as Cloud Run env vars):

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
- **frontend/proxy.ts** — Supabase SSR middleware equivalent. Both redirect branches must copy `supabaseResponse.cookies` onto the redirect response or token rotation silently breaks sessions.

## Test / lint / types state

**Backend**
- `pytest -v` → 143/143 pass
- `ruff check .` → clean
- `mypy app` → clean (strict=false)

**Frontend**
- `npx playwright test` (auth flow) → 9/9 pass (Chromium, local)
- `next build` → clean
- TypeScript: clean

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
| Phase 3b | Done | Next.js 16 frontend on Vercel — sign-in/up, expense CRUD, NL input hero, mobile responsive |
| Phase 3b.1 | Done | Auth hardening: 4 bugs fixed (onSelect→onClick, proxy.ts cookie propagation, sign-in server guard, window.location nav). 9 Playwright E2E scenarios green. |
| Phase 4a | Planned | Household foundation — household entity, member roles, invite model |
| Phase 4b | Planned | Shared + recurring + split engine |
| Phase 4c | Planned | Balances + UPI settle-up |
| Phase 4d | Planned | AI layer |
| Phase 4e | Planned | Group-first frontend |
| Phase 4f | Planned | PWA |
| Phase 4g | Planned | Join-by-link |

## Known issues / accepted debt
- No pagination on list endpoint — fine for personal scale.
- No LLM response caching — each parse/insight is a fresh Groq call.
- Groq free-tier rate limits (~30 rpm on 70B) — fine for personal use.
- `min_anomaly_samples=50`: seed.py (25 rows) falls below threshold; anomaly eval skipped by design. Run seed twice or use unit tests.
- Cold start 60–120s: expected on min-instances=0 free tier. Not a bug.
- Preview Vercel deploys are not CORS-permitted (only production URL + localhost:3000). Acceptable; revisit in Phase 4.
- Playwright E2E runs locally only — no CI integration yet. Will be addressed in a future phase.
