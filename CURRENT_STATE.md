# Current State: expense-tracker (post-Phase 2)

## Project goal
A personal expense tracker as a FastAPI service backed by SQLite. Single-user, runs locally, no auth. Evolution: v0 = CRUD + stats (done); Phase 1 = LLM features (done); Phase 2 = local ML (done); Phase 3 = production deployment (next).

## Directory structure (key files only)
```
expense-tracker/
├── pyproject.toml          # deps: fastapi, sqlalchemy 2.x sync, pydantic v2, uvicorn, pytest,
│                           #       httpx, ruff, mypy, groq, pydantic-settings, python-dotenv,
│                           #       pytest-mock, sentence-transformers, scikit-learn, prophet, joblib
├── README.md               # install / run / seed / curl examples + ML features section
├── spec.md                 # current spec (Phase 2.5)
├── CURRENT_STATE.md        # this file
├── .env                    # gitignored — GROQ_API_KEY lives here
├── .env.example            # committed template
├── expense_tracker.db      # SQLite, gitignored, created at runtime
├── eval-results/           # committed — eval + smoke artifacts
│   ├── phase2-eval-20260528.txt    # eval_ml.py output (categorizer + anomaly + forecast)
│   └── phase2-smoke-20260528.md   # live smoke test report (4 ML endpoints)
├── app/
│   ├── main.py             # FastAPI app + ALL 16 routes
│   ├── db.py               # SQLAlchemy engine + SessionLocal + get_db DI hook  [LOAD-BEARING]
│   ├── models.py           # Expense ORM model                                   [LOAD-BEARING]
│   ├── schemas.py          # Pydantic v2 schemas (v0 + Phase 1 + Phase 2 ML schemas)
│   ├── stats.py            # /stats/by-month + /stats/by-category queries
│   ├── config.py           # pydantic-settings Settings (GROQ + LLM + ML config) [LOAD-BEARING]
│   ├── llm.py              # Groq client wrapper: retry + 70B→8B fallback         [Phase 1, LOAD-BEARING]
│   ├── parser.py           # parse_expense_text() → ParsedExpense                 [Phase 1]
│   ├── insights.py         # monthly + category narrative generation               [Phase 1]
│   └── ml/                 # Phase 2 local ML package
│       ├── __init__.py
│       ├── embeddings.py   # sentence-transformers loader + embed() helper         [LOAD-BEARING]
│       ├── categorizer.py  # zero-shot cosine sim + logistic-regression trainer   [LOAD-BEARING]
│       ├── anomaly.py      # IsolationForest anomaly detection                    [LOAD-BEARING]
│       └── forecast.py     # Prophet spend forecaster + low-confidence fallback   [LOAD-BEARING]
├── scripts/
│   ├── seed.py             # 25 deterministic fake expenses (random.seed(42))
│   ├── eval_parser.py      # manual parser quality eval vs real Groq (not in CI)
│   └── eval_ml.py          # manual ML eval harness: categorizer + anomaly + forecast (not in CI)
└── tests/                  # 103/103 pass; conftest = in-memory SQLite + Depends override
    ├── conftest.py         # [LOAD-BEARING]
    ├── test_crud.py        # v0 CRUD endpoints
    ├── test_filters.py     # v0 list filters
    ├── test_health.py      # /health
    ├── test_stats.py       # /stats/by-month + /stats/by-category
    ├── test_llm.py         # LLM client unit tests (mocked)
    ├── test_llm_endpoints.py   # Phase 1 parse + from-text endpoints (mocked LLM)
    ├── test_insights.py    # Phase 1 insights endpoints (mocked LLM)
    ├── test_parser.py      # parse_expense_text() unit tests (mocked LLM)
    ├── test_embeddings.py  # embedding helper unit tests (Phase 2)
    ├── test_categorizer.py # suggest_category + train_categorizer (Phase 2)
    ├── test_anomaly.py     # detect_anomalies unit tests (Phase 2)
    ├── test_forecast.py    # forecast_spend unit tests (Phase 2)
    └── test_ml_endpoints.py    # Phase 2 ML HTTP endpoint integration tests
```

## Endpoints currently live (16 total)

**v0 (8):** GET /health, POST /expenses, GET /expenses (filters: ?category= ?since=), GET /expenses/{id}, PATCH /expenses/{id}, DELETE /expenses/{id}, GET /stats/by-month, GET /stats/by-category

**Phase 1 (4):** POST /expenses/parse, POST /expenses/from-text, GET /insights/monthly?month=, GET /insights/category?category=&since=

**Phase 2 (4):** POST /ml/categorize, POST /ml/train-categorizer, GET /ml/anomalies?since=, GET /ml/forecast?horizon=

## Load-bearing files (touch with care, escalate before modifying)
- **app/db.py** — `get_db` DI hook overridden in tests. Don't change its signature.
- **app/models.py** — `Expense` ORM model. Adding columns is fine; changing/removing existing ones breaks seed + stored data.
- **tests/conftest.py** — in-memory SQLite + per-test rollback + Depends override. Adding fixtures fine; modifying the `client` fixture breaks the whole suite.
- **app/llm.py** — Groq client with retry/fallback. Phase 1 parser + insights both depend on `get_llm_client`. Don't change its public surface without escalating.
- **app/config.py** — Settings is `@lru_cache`d. The whole app reads config through it. Phase 2 added: `embedding_model`, `min_train_per_category`, `min_anomaly_samples`, `min_forecast_months`, `models_dir`.
- **app/ml/embeddings.py** — singleton model loader. All three ML features depend on `embed()`. Model is lazy-loaded on first call (~5-10s cold start); cached globally via module-level `_model` variable.
- **app/ml/categorizer.py** — `suggest_category()` (zero-shot) and `train_categorizer()` (supervised, guarded by threshold). `DEFAULT_PROTOTYPES` used by the categorize endpoint to merge with user-defined DB categories.
- **app/ml/anomaly.py** — `detect_anomalies()` returns empty list below `min_anomaly_samples` threshold. Category-aware reasoning labels generated from per-category statistics.
- **app/ml/forecast.py** — `forecast_spend()` falls back to `low-confidence-average` mode below `min_forecast_months` threshold. Prophet runs in full mode when sufficient history exists.

## Conventions in use
- `from __future__ import annotations` at top of every Python file
- Type hints on every function; docstrings on non-trivial ones
- Pydantic v2 (`ConfigDict`, not nested `Config`)
- SQLAlchemy 2.x style (`Mapped[T]`, `mapped_column`, `select(...)`)
- Conventional commits; one concept per commit
- Single-currency (rupees), single-user (no auth)
- LLM never called from tests — always mocked. Real calls live only in scripts/eval_parser.py.
- ML models never loaded in tests — mocked via pytest-mock. Real model loads only in scripts/eval_ml.py and live server.

## Key decisions and why

**Inherited from v0/Phase 1:**
- **Sync SQLAlchemy:** simplicity; avoids async/sklearn/Prophet awkwardness in later phases.
- **SQLite:** single-user local; Postgres is Phase 3.
- **No Alembic:** `metadata.create_all` at startup; needed in Phase 3 when schema evolves on a deployed DB.
- **Free-form `category` string:** users define categories on the fly; Phase 2 categorization learns from / suggests against these.
- **Groq for LLM:** generous free tier, fast, user already had a key. 70B primary, 8B fallback on rate-limit.
- **`occurred_at` (date) vs `created_at` (datetime):** stats + time-series group on `occurred_at`.

**Phase 2 additions:**
- **Zero-shot-first categorization:** embed text + category prototypes via cosine similarity; no training required for day-one use. `suggest_category()` works immediately with any prototype list.
- **Supervised upgrade path guarded by threshold:** `train_categorizer()` refuses below `min_train_per_category` (default 30) examples per category. Returns a structured `refused-insufficient-data` response — never silently trains on too-small data.
- **Lazy model loading + module-level cache:** sentence-transformers model loaded once on first embed call, held in memory. Avoids repeated ~5-10s cold starts; compatible with sync SQLAlchemy.
- **IsolationForest with category-aware reasoning:** anomaly scores augmented with human-readable reason strings derived from per-category spend statistics. Threshold guard at `min_anomaly_samples` (default 20).
- **Prophet primary, low-confidence-average fallback:** forecast degrades gracefully below `min_forecast_months` (default 3) months of history. Mode is always surfaced in the response so callers know which path ran.
- **DB categories merged with defaults at request time:** `/ml/categorize` queries `distinct(Expense.category)` from DB and unions with `DEFAULT_PROTOTYPES`, so user-defined categories are always considered without any retraining step.

## Known issues / accepted debt
- `# noqa: B008` comments on `Depends(get_db)` are dead (modern ruff allowlists fastapi.Depends). Cosmetic; not this iteration.
- No pagination on list endpoint — fine for personal scale.
- No logging framework — `print` convention.
- No LLM response caching — each parse/insight is a fresh Groq call.
- Groq free-tier rate limits (~30 rpm on 70B) — fine for personal use, Phase 3 concern.
- **torch weight / deploy image size:** sentence-transformers pulls in torch (~2GB). Many free-tier deploy targets (Render/Railway) have size/memory caps it may exceed. Phase 3 must account for this — likely Cloud Run or a hosted embedding API.
- **42% anomaly flag rate on seeded data:** IsolationForest flagged 11/26 expenses. With only 26 seeded rows the contamination parameter is relatively generous; flag rate will stabilize with real usage data. Not a bug — observed behavior, Phase 3 concern.

## Test / lint / types state
- `pytest -v` → 103/103 pass (17 v0 + 37 Phase 1 + 49 Phase 2 — approximate breakdown)
- `ruff check .` → clean
- `mypy app` → clean (non-blocking; strict=false)
- `pytest-asyncio` deprecation warning: silenced via `asyncio_default_fixture_loop_scope = "function"` in pyproject.toml (Phase 2.5)
- Coverage not measured; criterion is per-feature test presence.

## Phase 2 eval observations (from eval-results/phase2-eval-20260528.txt and phase2-smoke-20260528.md)

### Categorizer (zero-shot, 8 canonical cases — 6/8, 75%)

| Text | Expected | Got | Score | Result |
|---|---|---|---|---|
| "lunch with Bob at Bombay Brasserie, 850" | food | food | 0.36 | pass |
| "uber to office 240" | transport | rent | 0.23 | **fail** |
| "₹1500 for groceries yesterday" | groceries | groceries | 0.58 | pass |
| "electricity bill 2340" | utilities | utilities | 0.37 | pass |
| "netflix 649" | entertainment | subscription | 0.31 | **fail** |
| "medicine 280" | health | health | 0.41 | pass |
| "5000 rent" | rent | rent | 0.72 | pass |
| "coffee 180" | food | food | 0.28 | pass |

**Observations (record only — no fixes this iteration):**
- "uber to office" → "rent" is a clear miss. Score 0.23 is low; "transport" prototype may not embed close enough to "uber to office" with `all-MiniLM-L6-v2`. The word "office" may anchor toward workspace/housing embeddings.
- "netflix" → "subscription" is a near-miss. "subscription" is a distractor prototype; removing it or adding "streaming" as a sub-label would likely fix this. Not fixing here.
- Confidence scores are generally low (0.23–0.72). The model was not trained on expense text; all scores reflect cosine similarity in a general-purpose embedding space.
- Accuracy will improve with a trained classifier once data threshold is met (30+ examples per category).

### Live smoke test of "swiggy order 480"
- `POST /ml/categorize {"text": "swiggy order 480"}` → `{"category":"utilities","score":0.19,"mode":"zero-shot"}`
- "swiggy" is a food-delivery brand not represented in `all-MiniLM-L6-v2`'s training vocabulary as a category signal. Score 0.19 is the lowest observed — reflects genuine ambiguity at 0-shot. Expected: food or food-delivery. Not fixing here.

### Anomaly detection (IsolationForest, 26 expenses)
- 11/26 flagged (42%) — high rate relative to dataset size.
- Reason strings are category-aware and human-readable (e.g., "2.4x your typical food spend", "rare category in your history (rent)").
- High flag rate expected on 26 seeded rows; IsolationForest contamination parameter is relatively generous at small N. Will stabilize with real usage data.
- Highest-scored flag: id=25, ₹16,363.64 rent (score 0.69) — rent appears only once in the seeded data, so "rare category" fires correctly.

### Forecast (Prophet, 4 months history)
- Prophet ran in **full mode** (not low-confidence-average fallback) — 4 months meets the `min_forecast_months=3` threshold.
- 3-month horizon: ₹24,382 → ₹30,548 → ₹36,921 (upward trend). Intervals ~±6k.
- Upward trend likely reflects an increasing spend pattern in the seeded data; plausible but not validated against actual spend intent.
- `/ml/forecast?horizon=2` smoke: consistent with eval output, prophet mode confirmed.

### Train-categorizer refusal
- `POST /ml/train-categorizer` → `{"status":"refused-insufficient-data","reason":"need >= 30 examples in at least 2 categories; 'utilities' has only 1.","n_examples":26,"n_categories":6,"metrics":null}`
- Threshold guard works correctly. Specific blocking reason surfaced (utilities has 1 example). Will auto-upgrade once data accumulates.

## Phase plan

| Phase | Status | Summary |
|---|---|---|
| v0 | Done | CRUD + stats, 8 endpoints, SQLite |
| Phase 1 | Done | LLM parse + from-text + insights, 4 endpoints, Groq |
| Phase 2 | Done | Local ML: categorizer + anomaly + forecast + train, 4 endpoints |
| Phase 2.5 | Done | Validation + cleanup: eval artifacts, pytest warning, CURRENT_STATE refresh |
| Phase 3 | Next | Production deployment: auth, Postgres/Alembic, frontend (Vercel), API (Cloud Run). May split into 3a (deploy) and 3b (auth/frontend). torch image size is the key deploy constraint to resolve first. |

## Open questions (for the human)
- Phase 3 deploy target: Cloud Run handles torch image size, but costs money. Confirm before starting.
- Auth approach for Phase 3: simple API key or full OAuth/session?
- Frontend framework for Phase 3: Next.js + Vercel, or keep CLI-first?
