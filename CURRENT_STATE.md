# Current State: expense-tracker (post-Phase 1)

## Project goal
A personal expense tracker as a FastAPI service backed by SQLite. Single-user, runs locally, no auth. Evolution: v0 = CRUD + stats; Phase 1 = LLM features (DONE); Phase 2 = classical/local ML (NEXT); Phase 3 = production deployment.

## Directory structure (key files only)
```
expense-tracker/
├── pyproject.toml          # deps: fastapi, sqlalchemy 2.x sync, pydantic v2, uvicorn, pytest,
│                           #       httpx, ruff, mypy, groq, pydantic-settings, python-dotenv, pytest-mock
├── README.md               # install / run / seed / curl examples + "LLM features" section
├── spec.v0.md              # v0 spec (history)
├── spec.md                 # current spec (Phase 2 once dropped in)
├── CURRENT_STATE.md         # this file
├── .env                    # gitignored — GROQ_API_KEY lives here
├── .env.example            # committed template
├── expense_tracker.db      # SQLite, gitignored, created at runtime
├── app/
│   ├── main.py             # FastAPI app + ALL routes (v0 CRUD/stats + Phase 1 LLM endpoints)
│   ├── db.py               # SQLAlchemy engine + SessionLocal + get_db DI hook  [LOAD-BEARING]
│   ├── models.py           # Expense ORM model                                   [LOAD-BEARING]
│   ├── schemas.py          # Pydantic v2 schemas (v0 CRUD + Phase 1 LLM schemas)
│   ├── stats.py            # /stats/by-month + /stats/by-category queries
│   ├── config.py           # pydantic-settings Settings (GROQ_API_KEY, LLM_MODEL, etc.)  [Phase 1]
│   ├── llm.py              # Groq client wrapper: retry + 70B→8B fallback         [Phase 1, LOAD-BEARING]
│   ├── parser.py           # parse_expense_text() → ParsedExpense                 [Phase 1]
│   └── insights.py         # monthly + category narrative generation             [Phase 1]
├── scripts/
│   ├── seed.py             # 25 deterministic fake expenses (random.seed(42))
│   └── eval_parser.py      # manual parser quality eval vs real Groq (not in CI)
└── tests/                  # 54/54 pass; conftest = in-memory SQLite + Depends override  [conftest LOAD-BEARING]
```

## Endpoints currently live
v0: POST /expenses, GET /expenses (filters: ?category= ?since=), GET /expenses/{id}, PATCH /expenses/{id}, DELETE /expenses/{id}, GET /stats/by-month, GET /stats/by-category, GET /health
Phase 1: POST /expenses/parse, POST /expenses/from-text, GET /insights/monthly?month=, GET /insights/category?category=&since=

## Load-bearing files (touch with care, escalate before modifying)
- **app/db.py** — `get_db` DI hook overridden in tests. Don't change its signature.
- **app/models.py** — `Expense` ORM model. Adding columns is fine; changing/removing existing ones breaks seed + stored data.
- **tests/conftest.py** — in-memory SQLite + per-test rollback + Depends override. Adding fixtures fine; modifying the `client` fixture breaks the whole suite.
- **app/llm.py** — Groq client with retry/fallback. Phase 1 parser + insights both depend on `get_llm_client`. Don't change its public surface without escalating.
- **app/config.py** — Settings is `@lru_cache`d. The whole app reads config through it.

## Conventions in use
- `from __future__ import annotations` at top of every Python file
- Type hints on every function; docstrings on non-trivial ones
- Pydantic v2 (`ConfigDict`, not nested `Config`)
- SQLAlchemy 2.x style (`Mapped[T]`, `mapped_column`, `select(...)`)
- Conventional commits; one concept per commit
- Single-currency (rupees), single-user (no auth)
- LLM never called from tests — always mocked. Real calls live only in scripts/eval_parser.py.

## Key decisions and why
- **Sync SQLAlchemy:** simplicity; avoids async/sklearn/Prophet awkwardness in later phases.
- **SQLite:** single-user local; Postgres is Phase 3.
- **No Alembic:** `metadata.create_all` at startup; needed in Phase 3 when schema evolves on a deployed DB.
- **Free-form `category` string:** users define categories on the fly; Phase 2 categorization learns from / suggests against these.
- **Groq for LLM:** generous free tier, fast, user already had a key. 70B primary, 8B fallback on rate-limit.
- **`occurred_at` (date) vs `created_at` (datetime):** stats + future time-series group on `occurred_at`.

## Known issues / accepted debt
- `# noqa: B008` comments on `Depends(get_db)` are dead (modern ruff allowlists fastapi.Depends). Cosmetic.
- No pagination on list endpoint — fine for personal scale.
- No logging framework — `print` convention.
- No LLM response caching — each parse/insight is a fresh Groq call. Easy to add later.
- Groq free-tier rate limits (~30 rpm on 70B) — fine for personal use, will bite under real multi-user load (Phase 3 concern).

## Test / lint / types state
- `pytest -v` → 54/54 pass (17 v0 + 37 Phase 1)
- `ruff check .` → clean
- `mypy app` → clean (non-blocking)
- Coverage not measured; criterion is per-feature test presence.

## Phase 2 forward-looking notes (for the spec, not yet built)
- **torch weight:** sentence-transformers pulls in torch (~2GB). Local install is slow; first model load ~5-10s. **Phase 3 deploy implication:** torch makes the deploy image huge — many free-tier platforms (Render/Railway) have size/memory caps it may exceed. May need a hosted embedding API or a torch-friendly deploy target in Phase 3.
- **Cold-start data:** only ~25-30 expenses exist. Phase 2 categorization must work zero-shot (embed text + category prototypes, cosine similarity) and only auto-upgrade to a trained classifier once enough labeled data accrues. Do NOT train a supervised classifier on the current tiny dataset.
- **Thin time-series:** ~4 months sparse data. Prophet will run but produce unreliable intervals; forecast must degrade gracefully below a data threshold and label low-confidence output clearly.

## Open questions (for the human)
- None blocking. Foundation is clean for Phase 2.
