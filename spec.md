# Project Spec: expense-tracker — Phase 3a (backend production-ready, GCP Cloud Run)

## Goal

Make the backend production-ready and deployed to GCP Cloud Run's always-free tier: multi-user via Supabase Auth (JWT validation), per-user data isolation, Alembic migrations, Supabase Postgres for prod (SQLite for local dev and tests). After Phase 3a, the backend is live, authenticated, and ready for a frontend (Phase 3b).

No frontend work. No Vercel. No sign-up UI.

## Current state (read-only context)
See CURRENT_STATE.md (post-Phase-2.6). Key facts:
- 16 endpoints, 115/115 tests, ruff + mypy clean
- Load-bearing: app/db.py, app/models.py, tests/conftest.py, app/llm.py, app/config.py
- Categorizer at 8/8 on canonical cases; anomaly gated below N=50
- All endpoints currently unauthenticated, single-user, SQLite-only
- User has Supabase project created with DATABASE_URL + SUPABASE_JWT_SECRET available in local .env

## Scope

### In scope (Phase 3a)

**Auth (Supabase JWT)**
- New module `app/auth.py`: validates Supabase JWT (HS256, secret from env var `SUPABASE_JWT_SECRET`), extracts user_id from `sub` claim (UUID string), exposes a FastAPI dependency `get_current_user_id() -> str`
- Use `pyjwt` (lightweight, well-maintained) — NOT `python-jose`
- Apply `get_current_user_id` dependency to ALL existing endpoints EXCEPT `GET /health`
- Tests override the dependency to return a fixed test UUID — no real JWT validation in pytest
- `POST /ml/train-categorizer` additionally gated behind `ADMIN_ENABLED=true` env var (defaults false)

**Multi-user data isolation**
- Add `user_id: str` (UUID, indexed, non-null) column to `Expense` ORM model
- All read queries in app/main.py, app/stats.py, app/insights.py, app/ml/anomaly.py, app/ml/forecast.py filter `WHERE user_id = :current_user_id`
- POST/PATCH endpoints stamp `user_id` from the current authenticated user
- 404 (not 403) on cross-user resource access — don't leak existence
- user_id is internal, NOT included in API responses

**Alembic migrations**
- Initialize Alembic in `migrations/` directory
- Migration 001: baseline schema (creates `expenses` table from current SQLAlchemy models — for fresh prod DB)
- Migration 002: add user_id column with index
- App startup runs migrations automatically when `RUN_MIGRATIONS_ON_STARTUP=true`; false for tests/local

**Postgres adapter**
- `app/db.py` reads `DATABASE_URL` from env. Default: `sqlite:///./expense_tracker.db` for local dev. Prod: Supabase Postgres URL.
- Add `psycopg2-binary` as dep (not asyncpg — we're sync everywhere)
- Tests continue using in-memory SQLite via existing override pattern
- `app/db.py` `get_db` signature unchanged (load-bearing)
- Use `sqlalchemy.pool.NullPool` for Supabase connection (Supabase pooler doesn't play well with SQLAlchemy's default pool on free tier)

**Configuration additions** (in `app/config.py`)
- `DATABASE_URL` (str)
- `SUPABASE_JWT_SECRET` (str)
- `SUPABASE_URL` (str)
- `ADMIN_ENABLED` (bool, default false)
- `RUN_MIGRATIONS_ON_STARTUP` (bool, default false)
- `CORS_ALLOWED_ORIGINS` (comma-separated list of origins, default empty)
- `.env.example` updated with all new variables + comments

**CORS**
- CORS middleware in `app/main.py` reading allowed origins from config
- Defaults: in prod, explicit allowlist via env var; in dev, localhost:3000 and localhost:5173

**Container & deploy (GCP Cloud Run, us-central1 free tier)**
- `Dockerfile`:
  - Base: `python:3.11-slim`
  - System deps for Prophet (build-essential, then removed after pip install if possible)
  - Install **CPU-only torch** explicitly: `pip install torch --index-url https://download.pytorch.org/whl/cpu` BEFORE pip-installing the project. This is critical — default torch is ~2GB CUDA-enabled; CPU-only is ~200MB.
  - Multi-stage build acceptable but not required; single stage is simpler
  - Copy app/, migrations/, alembic.ini, scripts/ (excluding tests/, eval-results/, .venv/, etc. via .dockerignore)
  - Listen on `${PORT}` (Cloud Run default 8080)
  - CMD: `exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}`
- `.dockerignore`: exclude `.venv/`, `tests/`, `eval-results/`, `__pycache__/`, `*.pyc`, `.env*`, `models/`, `expense_tracker.db`, `.git/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`
- `scripts/deploy.sh`: shell script with the gcloud commands the user runs (NOT executed by orchestrator — orchestrator generates it; user runs it). Includes:
  - `gcloud config set project [PROJECT_ID]` reminder
  - `gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com`
  - `gcloud run deploy expense-tracker --source . --region us-central1 --memory 2Gi --cpu 1 --max-instances 2 --min-instances 0 --timeout 300 --allow-unauthenticated --set-env-vars "DATABASE_URL=...,SUPABASE_JWT_SECRET=...,GROQ_API_KEY=...,RUN_MIGRATIONS_ON_STARTUP=true,ADMIN_ENABLED=false"`
  - Comments explaining each flag
- Service-level: `--allow-unauthenticated` (we do app-layer JWT, not platform-layer auth)

**Production-suitable logging**
- Replace remaining `print` calls with `logging` module
- Configure root logger at INFO with a structured-ish formatter (timestamp, level, module, message)
- Cloud Run captures stdout/stderr into Cloud Logging automatically — no extra config needed

**Seed script update**
- `scripts/seed.py` takes optional `--user-id UUID`; default deterministic local-dev UUID `00000000-0000-0000-0000-000000000001`
- Document this in the script's docstring

**Tests**
- All 115 baseline tests continue passing (under test user override)
- New test files:
  - `tests/test_auth.py` — valid JWT extracts user_id; missing JWT → 401; invalid JWT → 401; expired JWT → 401
  - `tests/test_isolation.py` — user A cannot read/modify/delete user B's expenses (covering all 16 endpoints); 404 on cross-user access
  - `tests/test_admin_gate.py` — `POST /ml/train-categorizer` returns 404 when `ADMIN_ENABLED=false`
  - `tests/test_migrations.py` — alembic upgrade head against in-memory SQLite produces the expected schema
- conftest.py addition: override `get_current_user_id` with a fixed test UUID. Keep existing fixture surface intact.

**README**
- "Production setup" section: Supabase project setup (already done by user; document for future), Cloud Run deploy steps, env var reference, JWT flow
- "Local development": SQLite + seed + how to override test user
- "Cold start expectations": one paragraph honestly explaining the 60-120s first-request latency on Cloud Run free tier

### Out of scope (Phase 3b or later)
- Frontend (any UI framework)
- Frontend deploy
- Sign-up / login UI
- Multi-currency, i18n
- Per-user rate limiting on LLM endpoints
- LLM response caching
- Background jobs, queues
- Webhooks, real-time
- Email/push notifications
- Admin UI
- Observability beyond stdout logging (no Sentry, no Cloud Monitoring custom metrics)
- Multi-region deploy
- Secret Manager integration (deferred — plain env vars are fine for 3a)
- Custom domain
- CI/CD pipeline (manual deploy in 3a)
- Cloud Run min-instances=1 (would cost money beyond free tier)

## Tech stack additions
- `pyjwt`
- `psycopg2-binary`
- `alembic`

If the executor wants more, escalate.

## Architecture (additions and modifications)

```
expense-tracker/
├── Dockerfile                        # NEW
├── .dockerignore                     # NEW
├── alembic.ini                       # NEW
├── migrations/                       # NEW
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 001_baseline_schema.py
│       └── 002_add_user_id.py
├── app/
│   ├── auth.py                       # NEW
│   ├── main.py                       # MODIFIED — auth dep, CORS, logging
│   ├── db.py                         # MODIFIED — DATABASE_URL env, NullPool for Postgres
│   ├── models.py                     # MODIFIED — user_id column
│   ├── config.py                     # MODIFIED — 6 new env vars
│   ├── stats.py                      # MODIFIED — user_id scoping
│   ├── insights.py                   # MODIFIED — user_id scoping
│   └── ml/
│       ├── anomaly.py                # MODIFIED — user_id scoping
│       └── forecast.py               # MODIFIED — user_id scoping
├── scripts/
│   ├── seed.py                       # MODIFIED — --user-id arg
│   └── deploy.sh                     # NEW (generated; user runs manually)
└── tests/
    ├── conftest.py                   # MODIFIED — auth dep override (additive only)
    ├── test_auth.py                  # NEW
    ├── test_isolation.py             # NEW
    ├── test_admin_gate.py            # NEW
    └── test_migrations.py            # NEW
```

conftest.py is load-bearing. Modification here is ADD-ONLY: add the new auth dependency override. Do not restructure existing fixtures. Escalate if anything else needs to change.

## Verification commands
```yaml
- name: tests
  cmd: pytest -v
  required: true
- name: lint
  cmd: ruff check .
  required: true
- name: types
  cmd: mypy app
  required: false
- name: migrations
  cmd: alembic upgrade head --sql
  required: false
```

## Interactive checkpoints (orchestrator pauses, asks human to act)

These are SCHEDULED human-action steps, not escalations:

**Checkpoint A — pre-iteration (already done by user):** Supabase project exists, `.env` populated with DATABASE_URL, SUPABASE_JWT_SECRET, SUPABASE_URL. Orchestrator confirms by reading `.env.example` and asking the user to confirm corresponding values are in `.env` (without printing them).

**Checkpoint B — after step 5 (Alembic init):** Orchestrator pauses. Asks the human to inspect the generated migration files (`migrations/versions/001_*.py` and `002_*.py`) before proceeding. The human eyeballs them, confirms they look right (table creation + user_id addition, no surprise drop/alter operations on unrelated columns), and replies "approved" or with specific concerns.

**Checkpoint C — after step 8 (Dockerfile + deploy.sh generated):** Orchestrator pauses with explicit gcloud commands for the human to run. Specifically:
1. Confirm `gcloud config get-value project` matches the desired GCP project
2. Run `gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com` if not already enabled
3. Run `bash scripts/deploy.sh` (or the equivalent gcloud command directly if on PowerShell — the orchestrator should also generate `scripts/deploy.ps1` for Windows convenience)
4. Wait for build (typically 5-10 min for first build with torch)
5. Paste back the resulting Cloud Run URL (format: `https://expense-tracker-xxxxx-uc.a.run.app`)

**Checkpoint D — after deploy:** Orchestrator runs a live smoke against the deployed URL:
- `GET /health` (expect 200; first request will be slow — 60-120s — that's the cold start)
- `GET /expenses` without auth (expect 401)
- Captures both to `eval-results/phase3a-deploy-smoke-YYYYMMDD.md`

## Escalation rules (orchestrator must ask before doing)
- Ask before installing dependencies beyond the three listed
- Ask if any existing test from the 115 baseline starts failing (modulo expected conftest auth override changes)
- Ask if Alembic autogeneration produces unexpected schema operations
- Ask if Supabase Postgres connection fails when running migrations locally
- Ask if any endpoint contract changes in a way that breaks existing clients
- Ask if Dockerfile build fails locally (test with `docker build .` before deploy if Docker is available)
- Ask if Cloud Run deploy returns a non-2xx during the live smoke after a reasonable cold-start wait (≥120s)
- Ask if the deployed app returns 500 on the first authenticated request (could be migration not run, env var missing, etc.)
- Request `/cost` checkpoints after step 3 (auth implemented + baseline tests green) and after Checkpoint D (deploy live). State: "please run /cost and paste the figure before I continue"

## Hard rules (do not violate)
- Do NOT modify app/llm.py
- Do NOT change get_db signature
- Do NOT commit any secret to git
- Do NOT remove or rename existing files
- Do NOT skip Alembic in favor of `metadata.create_all` against Postgres
- Do NOT make real Supabase/Cloud-Run/Groq calls inside pytest
- Do NOT use `python-jose` for JWT — `pyjwt` only
- Do NOT use asyncpg — sync everywhere (psycopg2)
- Do NOT add CUDA-enabled torch to the Dockerfile — CPU-only

## Budget
- Soft target: 120-180 minutes
- Hard cap: 25 executor invocations
- Cost-equivalent estimate: $15-22

## Success criteria (orchestrator: verify ALL before declaring done)
- All endpoints except `GET /health` require valid JWT (401 without, 401 with invalid, 401 with expired)
- User A cannot read/modify/delete user B's data (verified via test_isolation.py covering all 16 endpoints)
- `POST /ml/train-categorizer` returns 404 when `ADMIN_ENABLED=false`
- Alembic migrations from scratch produce schema matching SQLAlchemy models (no drift)
- App boots cleanly against both SQLite (local) and Postgres (prod) via DATABASE_URL switching
- 115 baseline tests still pass under updated conftest
- At least 12 new tests added across test_auth.py, test_isolation.py, test_admin_gate.py, test_migrations.py
- pytest -v: ≥127 tests, 0 fail; ruff clean; mypy clean
- Cloud Run deploy is live; `GET /health` against the cloud-run URL returns 200 (after cold start wait)
- `GET /expenses` without JWT against the deployed URL returns 401
- `eval-results/phase3a-deploy-smoke-YYYYMMDD.md` captured
- `CURRENT_STATE.md` refreshed: Phase 3a complete, live Cloud Run URL, new env vars, auth model documented, Phase 3b plan outlined
- `.env.example` lists ALL env vars with comments
- README has Production setup + Local development + Cold start expectations sections
- Dockerfile uses CPU-only torch (verify in the file)

## Build order
1. Add deps (pyjwt, psycopg2-binary, alembic) to pyproject.toml. Add 6 new env vars to app/config.py. Update .env.example. Verify 115 tests still pass.
2. `app/auth.py` with JWT validation + `get_current_user_id` dep. test_auth.py with mocked JWT scenarios. **[CHECKPOINT A: confirm .env values present]**
3. Update conftest.py to override `get_current_user_id` (additive). Verify 115 baseline tests still pass under override. **[ask user for /cost]**
4. Modify Expense model + all query sites for user_id scoping. Update scripts/seed.py for --user-id. test_isolation.py covering all 16 endpoints.
5. Initialize Alembic. Migration 001 (baseline), migration 002 (add user_id). test_migrations.py verifies upgrade-from-empty produces expected schema. **[CHECKPOINT B: human reviews migrations]**
6. app/db.py: switch to DATABASE_URL env var; NullPool for Postgres URLs; SQLite default. Verify local tests still pass with SQLite.
7. CORS middleware. Replace `print` with `logging` module. Admin gate for /ml/train-categorizer. test_admin_gate.py. Final pre-deploy verification: all tests pass, lint + types clean.
8. Generate Dockerfile (CPU-only torch), .dockerignore, scripts/deploy.sh, scripts/deploy.ps1. Document deploy steps in README. **[CHECKPOINT C: human runs deploy, pastes URL back]**
9. Live smoke against Cloud Run URL. Capture to eval-results/phase3a-deploy-smoke-<date>.md. **[CHECKPOINT D, ask user for /cost]**
10. Refresh CURRENT_STATE.md with deploy URL, new env vars, auth model, Phase 3b plan.
11. Final success-criteria walkthrough.
