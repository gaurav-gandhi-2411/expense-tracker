# expense-tracker

A single-user personal expense tracker built with FastAPI and SQLite. Exposes a REST API for creating, reading, updating, and deleting expense records, plus two aggregation endpoints (totals by month and by category). No authentication, no frontend — Phase 1 adds optional LLM-powered features (see below).

**Out of scope (v0):** auth, multi-user, frontend, Docker/CI, Alembic migrations, pagination, budgets, recurring expenses.

---

## Install

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1     # Windows PowerShell
# source .venv/bin/activate       # macOS / Linux
pip install -e ".[dev]"
```

If `pip install -e ".[dev]"` fails (missing build backend), use the direct fallback:

```bash
pip install fastapi "sqlalchemy>=2.0" "pydantic>=2" "uvicorn[standard]" pytest httpx ruff mypy
```

---

## Run

```bash
python -m uvicorn app.main:app --reload
```

- API base: `http://localhost:8000`
- Interactive docs (Swagger UI): `http://localhost:8000/docs`

---

## Seed

Populate the database with ~25 realistic fake expenses spread across the last 3 months:

```bash
python scripts/seed.py
```

Idempotent — clears existing rows before inserting. Uses `random.seed(42)`, so the output is deterministic.

---

## API examples

> **Windows PowerShell note:** `curl` is an alias for `Invoke-WebRequest` in PowerShell. Use `curl.exe` to get real curl, or run these commands from Git Bash / WSL.

### GET /health

```bash
curl http://localhost:8000/health
```

Response:

```json
{"status": "ok"}
```

---

### POST /expenses

```bash
curl -X POST http://localhost:8000/expenses \
  -H "Content-Type: application/json" \
  -d '{"amount": 250.0, "category": "food", "description": "dinner", "occurred_at": "2026-05-15"}'
```

Response: the created expense object with its assigned `id` and `created_at`.

---

### GET /expenses

List all expenses:

```bash
curl http://localhost:8000/expenses
```

Filter by category:

```bash
curl "http://localhost:8000/expenses?category=food"
```

Filter by date (expenses on or after the given date):

```bash
curl "http://localhost:8000/expenses?since=2026-04-01"
```

Both filters can be combined:

```bash
curl "http://localhost:8000/expenses?category=food&since=2026-04-01"
```

---

### GET /expenses/{id}

```bash
curl http://localhost:8000/expenses/1
```

Returns 404 if the expense does not exist.

---

### PATCH /expenses/{id}

Partial update — only send the fields you want to change:

```bash
curl -X PATCH http://localhost:8000/expenses/1 \
  -H "Content-Type: application/json" \
  -d '{"amount": 300.0, "description": "dinner + drinks"}'
```

---

### DELETE /expenses/{id}

```bash
curl -X DELETE http://localhost:8000/expenses/1
```

Returns 204 No Content on success, 404 if not found.

---

### GET /stats/by-month

```bash
curl http://localhost:8000/stats/by-month
```

Response:

```json
[
  {"month": "2026-03", "total": 4120.50},
  {"month": "2026-04", "total": 6340.00},
  {"month": "2026-05", "total": 2890.75}
]
```

---

### GET /stats/by-category

```bash
curl http://localhost:8000/stats/by-category
```

Response:

```json
[
  {"category": "food", "total": 5230.00},
  {"category": "transport", "total": 1800.25},
  {"category": "utilities", "total": 3100.00}
]
```

---

## LLM features

Phase 1 adds two LLM-powered capabilities on top of the v0 CRUD layer: natural-language expense input (type a sentence, get a structured expense) and narrative spending insights (a short prose summary of a month or category). Both features are backed by the Groq free tier using Llama 3.3 70B Versatile as the primary model and Llama 3.1 8B Instant as the fallback when the primary hits rate limits. Four new endpoints are added: `POST /expenses/parse`, `POST /expenses/from-text`, `GET /insights/monthly`, and `GET /insights/category`.

### Setup

1. Sign up at https://console.groq.com (free tier).
2. Generate an API key.
3. Copy `.env.example` to `.env`:

   ```bash
   cp .env.example .env
   ```

4. Edit `.env` and set `GROQ_API_KEY=gsk_...` (your real key).
5. Install the LLM-related deps (already declared in pyproject.toml):

   ```bash
   pip install -e ".[dev]"
   ```

### Environment variables

| Var | Default | Description |
| --- | --- | --- |
| `GROQ_API_KEY` | (required) | Your Groq API key |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | Primary model |
| `LLM_FALLBACK_MODEL` | `llama-3.1-8b-instant` | Used if the primary hits rate limits |

### POST /expenses/parse

Parse a free-text expense description into a structured `ParsedExpense` object. Does **not** save the record — use this to preview the extraction before committing.

```bash
curl -X POST http://localhost:8000/expenses/parse \
  -H "Content-Type: application/json" \
  -d '{"text": "lunch with Bob at Bombay Brasserie, 850"}'
```

Response:

```json
{
  "amount": 850.0,
  "category": "food",
  "description": "lunch with Bob at Bombay Brasserie",
  "occurred_at": "2026-05-22",
  "confidence": 0.95
}
```

---

### POST /expenses/from-text

Parse a free-text description **and** save the resulting expense in one step. Returns the full saved expense including its assigned `id` and `created_at`.

```bash
curl -X POST http://localhost:8000/expenses/from-text \
  -H "Content-Type: application/json" \
  -d '{"text": "lunch with Bob at Bombay Brasserie, 850"}'
```

Response:

```json
{
  "id": 26,
  "amount": 850.0,
  "category": "food",
  "description": "lunch with Bob at Bombay Brasserie",
  "occurred_at": "2026-05-22",
  "created_at": "2026-05-22T14:32:10"
}
```

---

### GET /insights/monthly

Generate a narrative prose summary of spending for a given calendar month. Returns an `Insight` object with a `narrative` field and supporting stats.

```bash
curl "http://localhost:8000/insights/monthly?month=2026-05"
```

Response:

```json
{
  "scope": "month:2026-05",
  "narrative": "In May 2026 you spent ₹9,350 across 14 transactions, averaging ₹780.50 on active days. Food was the heaviest category at ₹3,200. Spending was concentrated in the first two weeks.",
  "stats": {
    "total": 9350.0,
    "count": 14.0,
    "avg_per_day": 780.5,
    "top_category_total": 3200.0
  },
  "generated_at": "2026-05-22T14:35:00"
}
```

Returns `400` if `month` is malformed, `503` if the LLM is unavailable. Returns `200` with a "No expenses recorded for this month." narrative (no LLM call) when the month has no rows.

---

### GET /insights/category

Generate a narrative summary scoped to a single category. `category` is required; `since` (a `YYYY-MM-DD` date) is optional and filters to expenses on or after that date.

```bash
curl "http://localhost:8000/insights/category?category=food&since=2026-05-01"
```

Response:

```json
{
  "scope": "category:food",
  "narrative": "Since May 1 you've spent ₹3,200 on food across 7 transactions. The largest single expense was ₹850 at Bombay Brasserie. Average transaction is ₹457.14.",
  "stats": {
    "total": 3200.0,
    "count": 7.0,
    "avg_amount": 457.14,
    "max_amount": 850.0
  },
  "generated_at": "2026-05-22T14:36:00"
}
```

Returns `503` if the LLM is unavailable. Returns `200` with a `"No expenses recorded for category '{category}'."` narrative when no rows match the filter.

---

### Eval script

`scripts/eval_parser.py` runs all 8 canonical parser test cases against the real Groq API and reports per-case pass/fail with a diff between expected and actual output. It is used manually after parser or prompt changes to gauge extraction quality. It is **not** in the CI test path.

```bash
python scripts/eval_parser.py
python scripts/eval_parser.py --json   # machine-readable output
```

Requires `GROQ_API_KEY` set in `.env`.

---

## ML features

Phase 2 adds three local ML capabilities on top of the Phase 1 LLM layer: automatic expense categorization via sentence embeddings, anomaly detection using IsolationForest, and monthly spend forecasting using Prophet. All three run entirely locally — no API calls, no cost after the first model download. Four new endpoints are added: `POST /ml/categorize`, `POST /ml/train-categorizer`, `GET /ml/anomalies`, and `GET /ml/forecast`.

### Setup

Install deps (already declared in `pyproject.toml`):

```bash
pip install -e ".[dev]"
```

The first call to any categorize endpoint will download the `all-MiniLM-L6-v2` sentence-transformers model (~90 MB) and cache it under `~/.cache/huggingface/`. Plan for 30–60 s first-call latency on a cold start; subsequent calls are fast.

### Environment variables

| Var | Default | Description |
| --- | --- | --- |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | sentence-transformers model name |
| `MIN_TRAIN_PER_CATEGORY` | `30` | Min labeled examples per category before training is allowed |
| `MIN_ANOMALY_SAMPLES` | `20` | Min total expenses before anomaly detection runs |
| `MIN_FORECAST_MONTHS` | `3` | Min historical months before Prophet runs; below this, low-confidence average is returned |
| `MODELS_DIR` | `models` | Directory for persisted trained classifier (gitignored) |

### POST /ml/categorize

Suggest a category for a raw expense description. Uses zero-shot prototype matching by default; switches to the trained LogisticRegression classifier automatically when `models/categorizer.joblib` exists on disk.

```bash
curl -X POST http://localhost:8000/ml/categorize \
  -H "Content-Type: application/json" \
  -d '{"text": "lunch with team at Bombay Brasserie"}'
```

Response:

```json
{
  "category": "food",
  "score": 0.87,
  "mode": "zero-shot"
}
```

---

### POST /ml/train-categorizer

Train a LogisticRegression classifier on all labeled expenses in the DB. Persists the model to `models/categorizer.joblib` on success. Refuses if any category has fewer than 30 examples or fewer than 2 qualifying categories are found.

```bash
curl -X POST http://localhost:8000/ml/train-categorizer
```

Response (trained):

```json
{
  "status": "trained",
  "reason": "trained on 120 examples across 5 categories",
  "n_examples": 120,
  "n_categories": 5,
  "metrics": {"accuracy": 0.94}
}
```

Response (refused):

```json
{
  "status": "refused-insufficient-data",
  "reason": "need >= 30 examples in at least 2 categories; 'rent' has only 4.",
  "n_examples": 28,
  "n_categories": 3,
  "metrics": null
}
```

---

### GET /ml/anomalies

Detect unusual expenses using IsolationForest. Returns an empty list when fewer than 20 total expenses exist (avoids noisy results on sparse data). The optional `since` query parameter restricts the input window.

```bash
curl "http://localhost:8000/ml/anomalies?since=2026-03-01"
```

Response:

```json
[
  {
    "expense_id": 17,
    "amount": 14500.0,
    "category": "rent",
    "reason": "3.2x your typical rent spend",
    "score": 0.4821
  }
]
```

Returns an empty array (`[]`) when fewer than `MIN_ANOMALY_SAMPLES` expenses are found.

---

### GET /ml/forecast

Forecast monthly spend for the next N months using Prophet. Returns the `"low-confidence-average"` mode when fewer than 3 months of history are available, projecting a simple average with wide uncertainty bands instead of fitting a seasonal model.

```bash
curl "http://localhost:8000/ml/forecast?horizon=3"
```

Response (Prophet path):

```json
{
  "horizon_months": 3,
  "mode": "prophet",
  "note": "Prophet forecast based on 5 months of history.",
  "points": [
    {"month": "2026-06", "predicted": 8420.50, "lower": 6100.00, "upper": 10800.00},
    {"month": "2026-07", "predicted": 8750.00, "lower": 6350.00, "upper": 11200.00},
    {"month": "2026-08", "predicted": 9100.00, "lower": 6600.00, "upper": 11650.00}
  ]
}
```

Response (low-confidence fallback):

```json
{
  "horizon_months": 3,
  "mode": "low-confidence-average",
  "note": "Only 2 months of history; using simple average as a low-confidence projection.",
  "points": [
    {"month": "2026-06", "predicted": 7200.00, "lower": 3600.00, "upper": 10800.00},
    {"month": "2026-07", "predicted": 7200.00, "lower": 3600.00, "upper": 10800.00},
    {"month": "2026-08", "predicted": 7200.00, "lower": 3600.00, "upper": 10800.00}
  ]
}
```

---

### Eval script

`scripts/eval_ml.py` is a manual quality check that loads the real embedding model and runs all three ML features against real data. It is **not** in the CI test path.

```bash
# Run all three sections (requires seeded DB for anomaly + forecast)
python scripts/eval_ml.py

# Skip embedding-heavy categorizer section
python scripts/eval_ml.py --skip-categorizer

# Run only the categorizer section (no DB required)
python scripts/eval_ml.py --skip-anomaly --skip-forecast

# Run only anomaly + forecast (no embedding model load)
python scripts/eval_ml.py --skip-categorizer
```

Seed the DB first for anomaly and forecast sections:

```bash
python scripts/seed.py
python scripts/eval_ml.py
```

---

### Phase 3 deploy note

`sentence-transformers` pulls PyTorch (~2 GB). The local install is heavy and first model load is slow (30–60 s on cold start). The resulting Docker image will be large, and some free-tier hosts (Render, Railway) may exceed their size or memory caps.

**Phase 3 concern (not a Phase 2 blocker):** Phase 3 may switch to a hosted embedding API (e.g. OpenAI embeddings, Cohere, or Voyage AI) or a torch-friendly deploy target (e.g. Fly.io with a sized VM) to keep the container lean and startup time acceptable. This decision will be documented in an ADR when it lands.

---

## Run tests

```bash
pytest -v
ruff check .
mypy app
```

---

## Project layout

```
expense-tracker/
├── pyproject.toml
├── README.md
├── .env.example
├── models/            # persisted trained classifier (gitignored)
├── app/
│   ├── config.py      # pydantic-settings Settings
│   ├── db.py          # SQLAlchemy engine + session factory
│   ├── insights.py    # narrative spending insights via LLM
│   ├── llm.py         # Groq client wrapper (retry + fallback)
│   ├── main.py        # FastAPI app + all routes
│   ├── models.py      # ORM model (Expense)
│   ├── parser.py      # text → ParsedExpense via LLM
│   ├── schemas.py     # Pydantic schemas (create / update / read)
│   ├── stats.py       # Aggregation queries (by-month, by-category)
│   └── ml/
│       ├── __init__.py
│       ├── embeddings.py   # sentence-transformers wrapper (lazy init)
│       ├── categorizer.py  # zero-shot + trained category suggestion
│       ├── anomaly.py      # IsolationForest anomaly detection
│       └── forecast.py     # Prophet monthly spend forecasting
├── scripts/
│   ├── eval_parser.py # manual quality check against real Groq API
│   ├── eval_ml.py     # manual quality check for Phase 2 ML features (NOT CI)
│   └── seed.py        # Deterministic fake-data seeder
└── tests/
    ├── conftest.py          # In-memory DB fixture + TestClient
    ├── test_crud.py
    ├── test_filters.py
    ├── test_health.py
    ├── test_insights.py
    ├── test_llm.py
    ├── test_llm_endpoints.py
    ├── test_parser.py
    ├── test_stats.py
    ├── test_embeddings.py
    ├── test_categorizer.py
    ├── test_anomaly.py
    ├── test_forecast.py
    └── test_ml_endpoints.py
```
