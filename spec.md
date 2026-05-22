# Project Spec: expense-tracker — Phase 2 (local ML)

## Goal

Add three local, free, offline ML capabilities on top of the existing service:

1. **Auto-categorization** — given expense text, suggest a category using sentence-transformers embeddings. Zero-shot first (cosine similarity to category prototypes, no training data needed); auto-upgrades to a trained classifier once enough labeled data exists.
2. **Anomaly detection** — flag unusual expenses using IsolationForest, with a human-readable reason per flag.
3. **Spend forecasting** — project future monthly spend with confidence intervals using Prophet, degrading gracefully when historical data is thin.

All three run locally with no API calls and no cost. The build sits ON TOP of v0 + Phase 1. The orchestrator MUST read CURRENT_STATE.md before planning.

## Current state (read-only context)
See CURRENT_STATE.md. Key points:
- v0 + Phase 1 complete: 12 endpoints, 54/54 tests, ruff + mypy clean
- Load-bearing files: app/db.py, app/models.py, tests/conftest.py, app/llm.py, app/config.py
- ~25-30 expenses exist total — NOT enough to train a supervised classifier. Categorization MUST work zero-shot.
- torch (~2GB) is acceptable here but has Phase 3 deploy implications (noted, not a Phase 2 concern)

## Scope

### In scope (Phase 2)
New package `app/ml/` containing:
- `app/ml/__init__.py`
- `app/ml/embeddings.py` — lazy-loaded, cached sentence-transformers model (`all-MiniLM-L6-v2`); function to embed a list of texts
- `app/ml/categorizer.py` — `suggest_category(text: str) -> CategorySuggestion`. Zero-shot mode: embed text, compare to embedded category prototypes, return best match + score. Trained mode: if a persisted classifier exists at `models/categorizer.joblib`, use it instead. A `train_categorizer()` function builds + persists the classifier from labeled expenses, but only when there are at least `MIN_TRAIN_PER_CATEGORY` (default 30) examples in 2+ categories — otherwise it refuses and logs why.
- `app/ml/anomaly.py` — `detect_anomalies(expenses) -> list[AnomalyFlag]` using IsolationForest on features (amount, day-of-week, category-frequency, rolling category mean deviation). Each flag includes a plain-language reason (e.g. "3.2x your typical food spend"). Degrades gracefully below `MIN_ANOMALY_SAMPLES` (default 20) by returning an empty list with a note.
- `app/ml/forecast.py` — `forecast_spend(horizon_months: int) -> ForecastResult` using Prophet on the monthly-aggregated time series. Below `MIN_FORECAST_MONTHS` (default 3) of data, returns a clearly-labeled low-confidence simple-average projection instead of Prophet output.

New endpoints in `app/main.py`:
- `POST /ml/categorize` — body `{"text": "..."}` → `CategorySuggestion` (suggested category + score + mode used)
- `GET /ml/anomalies?since=YYYY-MM-DD` → list of `AnomalyFlag`
- `GET /ml/forecast?horizon=N` → `ForecastResult` (N months ahead, default 1)
- `POST /ml/train-categorizer` → triggers training if data threshold met; returns status (trained / refused-insufficient-data) + metrics if trained

New Pydantic schemas in `app/schemas.py`:
- `CategorySuggestion` (category, score, mode: "zero-shot"|"trained")
- `AnomalyFlag` (expense_id, amount, category, reason, score)
- `ForecastResult` (horizon_months, points: list of {month, predicted, lower, upper}, mode: "prophet"|"low-confidence-average", note)

Config additions in `app/config.py`:
- `EMBEDDING_MODEL` (default `all-MiniLM-L6-v2`)
- `MIN_TRAIN_PER_CATEGORY` (default 30)
- `MIN_ANOMALY_SAMPLES` (default 20)
- `MIN_FORECAST_MONTHS` (default 3)
- `MODELS_DIR` (default `models/`)

Tests:
- `tests/test_categorizer.py` — mock the embedding model; assert zero-shot picks the right prototype for clear cases; assert trained-mode path is taken when a model file exists; assert `train_categorizer` refuses below threshold
- `tests/test_anomaly.py` — synthetic data with an injected obvious outlier; assert it's flagged with a reason; assert graceful empty result below sample threshold
- `tests/test_forecast.py` — synthetic monthly series; assert Prophet path returns well-formed points above threshold; assert low-confidence-average path below threshold; assert no crash on empty data
- `tests/test_ml_endpoints.py` — endpoint integration with mocked ML layer

Manual eval script:
- `scripts/eval_ml.py` — loads the REAL embedding model, runs categorization against the Phase 1 parser test cases + any real expenses, prints zero-shot accuracy; runs anomaly detection + forecast on real seeded data and prints results. NOT in CI (heavy, needs torch). For the human to gauge real quality.

README: new "ML features" section — what each does, the zero-shot vs trained behavior, data thresholds, example curls, how to run eval_ml.py, the torch/Phase-3 caveat.

### Out of scope (Phase 3 or later — do NOT build now)
- Authentication / multi-user (Phase 3)
- Frontend / UI (Phase 3)
- Deployment, Docker, CI (Phase 3)
- Postgres migration / Alembic (Phase 3)
- Retraining schedules, model versioning systems, MLflow, experiment tracking
- GPU usage — CPU only
- Hosted embedding APIs — local sentence-transformers only for Phase 2
- Hyperparameter tuning frameworks — sensible fixed defaults only
- Real-time / streaming anomaly detection — batch over stored data only

## Tech stack additions
- `sentence-transformers` (pulls in torch — accepted)
- `scikit-learn` (IsolationForest, LogisticRegression, train/test utils)
- `prophet`
- `joblib` (persist trained classifier)
- `numpy`, `pandas` (likely transitive via the above; pin if added directly)

No other new dependencies. If the executor wants one, escalate. Note: prophet can be install-finicky on Windows — if pip install fails, escalate with the error rather than trying exotic workarounds.

## Architecture (additions and modifications only)

```
expense-tracker/
├── models/                      # NEW (gitignored) — persisted trained classifier
├── app/
│   ├── ml/                      # NEW package
│   │   ├── __init__.py
│   │   ├── embeddings.py
│   │   ├── categorizer.py
│   │   ├── anomaly.py
│   │   └── forecast.py
│   ├── main.py                  # MODIFIED — add 4 ML endpoints
│   ├── schemas.py               # MODIFIED — add CategorySuggestion, AnomalyFlag, ForecastResult
│   └── config.py                # MODIFIED — add ML config values
├── scripts/
│   └── eval_ml.py               # NEW — manual ML quality eval (real model)
└── tests/
    ├── test_categorizer.py      # NEW
    ├── test_anomaly.py          # NEW
    ├── test_forecast.py         # NEW
    └── test_ml_endpoints.py     # NEW
```

## Key design rules
- **Categorization is zero-shot by default.** Do NOT train a classifier on the current tiny dataset. The trained path only activates when a persisted model exists AND was built above threshold.
- **Model loading is lazy + cached.** The sentence-transformers model loads on first use, not at import / app startup, and is cached (module-level singleton or lru_cache). App startup must stay fast.
- **Tests never load the real embedding model or train Prophet on real data.** Mock the embedding function and use small synthetic arrays. The only place real models load is scripts/eval_ml.py.
- **Every ML output degrades gracefully.** Thin data → labeled low-confidence response, never a crash and never a confidently-wrong number.
- **Category prototypes** come from the distinct categories already present in the DB, plus a small built-in default list (food, transport, groceries, utilities, entertainment, health, rent, other) so zero-shot works even on an empty DB.

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
```
Run all after every executor pass. scripts/eval_ml.py is NOT in verification (needs torch + real model).

## Subagent usage rules
- `executor` for all code/config writes
- `verifier` for all test/lint/types runs
- Orchestrator does NOT write code

## Escalation rules (orchestrator must ask before doing)
- Ask before installing any dependency beyond those in "Tech stack additions"
- Ask before modifying any load-bearing file (CURRENT_STATE.md list)
- Ask if a single executor pass would touch more than 6 files
- Ask if verification fails 3 times in a row on the same check
- Ask if any existing v0 or Phase 1 test starts failing
- Ask if any existing endpoint's behavior changes
- Ask if `pip install prophet` or `pip install sentence-transformers` fails (Windows install issues are real — surface the error, don't improvise)
- Ask if a test would need to load the real embedding model or hit a real API
- Run `/cost` after the categorizer is working (end of feature 1) and after forecast is working (end of feature 3)

## Hard rules (do not violate)
- Do NOT modify app/db.py, app/models.py, tests/conftest.py, app/llm.py public surface
- Do NOT change any existing endpoint signature or behavior
- Do NOT remove or rename any existing file
- Do NOT train a supervised classifier on the current dataset — zero-shot only until threshold
- Do NOT load real ML models or call real APIs inside pytest — mock everything
- Do NOT commit the models/ directory or any .joblib artifacts (gitignore them)
- CPU only — no CUDA/GPU code paths

## Budget
- Soft target: 1 CC session (this is heavier than prior phases — torch install + 3 ML subsystems)
- Hard cap: stop and escalate after 20 executor invocations without "done"
- Each ML feature is committed independently, so partial progress survives if a later feature stalls
- Cost checks after feature 1 (categorizer) and feature 3 (forecast)

## Success criteria (orchestrator: verify ALL before declaring done)
- All 4 new ML endpoints reachable and pass their tests
- All 54 existing tests still pass (no regression)
- `pytest -v` reports: ≥70 tests pass, 0 fail
- `ruff check .` clean
- `mypy app` clean
- Categorizer works zero-shot with no trained model present (verified by a test with no model file)
- `train_categorizer` correctly REFUSES on the current below-threshold dataset (verified by test)
- Anomaly detection flags an injected synthetic outlier with a reason (verified by test)
- Forecast returns Prophet output above threshold and labeled low-confidence output below it (both verified by tests)
- models/ is gitignored; no model artifacts committed
- README has an "ML features" section covering all three features, the thresholds, and the torch/Phase-3 caveat
- scripts/eval_ml.py is syntactically valid and runnable (orchestrator verifies it imports/parses, does NOT run it against real torch)

## Build order (recommended; orchestrator may adjust)
1. Add deps to pyproject.toml; gitignore models/ and *.joblib; add ML config values to app/config.py. Install deps (escalate if prophet/sentence-transformers install fails on Windows).
2. app/ml/embeddings.py — lazy cached model loader + embed function. Test with mocked SentenceTransformer.
3. app/ml/categorizer.py — zero-shot + trained-path + threshold-guarded train function. Tests (mocked embeddings). **[cost check after this]**
4. app/schemas.py — CategorySuggestion. app/main.py — POST /ml/categorize + POST /ml/train-categorizer. Endpoint tests (mocked ML).
5. app/ml/anomaly.py — IsolationForest + reason generation + graceful thin-data. Tests (synthetic outlier).
6. app/schemas.py — AnomalyFlag. app/main.py — GET /ml/anomalies. Endpoint tests.
7. app/ml/forecast.py — Prophet + low-confidence fallback + graceful empty. Tests (synthetic series). **[cost check after this]**
8. app/schemas.py — ForecastResult. app/main.py — GET /ml/forecast. Endpoint tests.
9. scripts/eval_ml.py — manual real-model eval harness (verify it parses; don't run against torch).
10. README "ML features" section.
11. Final verification — all green, no regression, success-criteria walkthrough. Note in final report that CURRENT_STATE.md will need another refresh before Phase 3.
