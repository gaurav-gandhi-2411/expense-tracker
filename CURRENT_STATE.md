# Current State: expense-tracker (post-v0)

## Project goal
A personal expense tracker as a FastAPI service backed by SQLite. Single-user, runs locally, no auth. Phase 1 of evolution: adding LLM-powered features. Phase 2: classical ML. Phase 3: production deployment.

## Directory structure (key files only)
```
expense-tracker/
├── pyproject.toml         # deps: fastapi, sqlalchemy 2.x sync, pydantic v2, uvicorn, pytest, httpx, ruff, mypy
├── README.md              # install / run / seed / curl examples for all 8 endpoints
├── spec.md                # v0 spec (now superseded — kept for history)
├── CURRENT_STATE.md       # this file
├── expense_tracker.db     # SQLite, gitignored, created at runtime
├── app/
│   ├── main.py            # FastAPI app + all routes
│   ├── db.py              # SQLAlchemy engine + SessionLocal
│   ├── models.py          # Expense ORM model
│   ├── schemas.py         # Pydantic v2 schemas (create/update/read)
│   └── stats.py           # /stats/by-month + /stats/by-category queries
├── scripts/
│   └── seed.py            # 25 deterministic fake expenses (random.seed(42))
└── tests/                 # 17/17 pass, conftest uses in-memory SQLite + dependency override
```

## Load-bearing files (touch with care)
- **app/db.py** — `get_db` is the DI hook overridden in tests. Don't change its signature.
- **app/models.py** — `Expense` ORM model. Adding columns is fine; changing existing column types or dropping columns breaks the seed script and stored data.
- **tests/conftest.py** — fixture wiring is non-obvious (in-memory SQLite + per-test rollback + Depends override). Adding fixtures is fine; modifying the existing `client` fixture without understanding it will break the whole suite.

## Conventions in use
- `from __future__ import annotations` at top of every Python file
- Type hints on every function
- Docstrings on non-trivial functions
- Pydantic v2 (not v1) — use `model_config = ConfigDict(...)`, not nested `Config` classes
- SQLAlchemy 2.x style — `Mapped[T]`, `mapped_column`, `select(...)` queries (not legacy `Query`)
- Conventional commits (`feat:`, `fix:`, `test:`, `chore:`, etc.)
- Single-currency (rupees), single-user (no auth) — assumptions baked into the data model

## Key decisions and why
- **Sync SQLAlchemy (not async):** v0 prioritized simplicity. Mixing async I/O with sklearn / Prophet in later phases would be awkward; staying sync keeps it consistent.
- **SQLite (not Postgres):** single-user, local; moving to Postgres is Phase 3 work, not a Phase 1 concern.
- **No Alembic:** `metadata.create_all` at startup. Will need Alembic in Phase 3 when schema evolves on a deployed DB.
- **Free-form `category` string (not enum):** users define categories on the fly via the API. Phase 2 auto-categorization will learn from this.
- **`occurred_at` (date) vs `created_at` (datetime):** date of expense is what user reports; created_at is row insertion. Stats endpoints group by `occurred_at`.

## Known issues / accepted debt
- `# noqa: B008` comments on `Depends(get_db)` in app/main.py are dead — modern ruff allowlists `fastapi.Depends`. Cosmetic, not blocking.
- No pagination on list endpoint — fine for personal use, will need it if data grows past a few thousand rows.
- No logging framework — `print` is the convention for now (per v0 spec).
- No request validation beyond Pydantic — no rate limiting, no input sanitization beyond what Pydantic gives you. Acceptable while there's no auth and it runs locally.

## Test / lint / types state
- `pytest -v` → 17/17 pass
- `ruff check .` → clean
- `mypy app` → clean (non-blocking per spec, but currently clean)
- Coverage not measured; success criterion was "≥1 test per endpoint," not a coverage target

## Phase plan (future scope, not for this iteration)
1. **Phase 1 (next iteration):** LLM-powered natural-language input + insight generation via Groq free tier
2. **Phase 2:** Classical ML — auto-categorization (sentence-transformers + classifier), anomaly detection (IsolationForest), forecasting (Prophet)
3. **Phase 3:** Production — Supabase auth (free tier), frontend (Streamlit or React), deploy on Railway/Fly free tier, Alembic migrations, Postgres on Neon free tier

## Open questions (for the human, not the orchestrator)
- None at this point. v0 is a clean foundation.
