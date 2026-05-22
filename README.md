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
├── app/
│   ├── config.py      # pydantic-settings Settings
│   ├── db.py          # SQLAlchemy engine + session factory
│   ├── insights.py    # narrative spending insights via LLM
│   ├── llm.py         # Groq client wrapper (retry + fallback)
│   ├── main.py        # FastAPI app + all routes
│   ├── models.py      # ORM model (Expense)
│   ├── parser.py      # text → ParsedExpense via LLM
│   ├── schemas.py     # Pydantic schemas (create / update / read)
│   └── stats.py       # Aggregation queries (by-month, by-category)
├── scripts/
│   ├── eval_parser.py # manual quality check against real Groq API
│   └── seed.py        # Deterministic fake-data seeder
└── tests/
    ├── conftest.py    # In-memory DB fixture + TestClient
    ├── test_crud.py
    ├── test_filters.py
    ├── test_health.py
    ├── test_insights.py
    ├── test_llm.py
    ├── test_llm_endpoints.py
    ├── test_parser.py
    └── test_stats.py
```
