# expense-tracker

A single-user personal expense tracker built with FastAPI and SQLite. Exposes a REST API for creating, reading, updating, and deleting expense records, plus two aggregation endpoints (totals by month and by category). No authentication, no frontend — this is v0, a local dev tool.

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
├── app/
│   ├── main.py        # FastAPI app + all routes
│   ├── db.py          # SQLAlchemy engine + session factory
│   ├── models.py      # ORM model (Expense)
│   ├── schemas.py     # Pydantic schemas (create / update / read)
│   └── stats.py       # Aggregation queries (by-month, by-category)
├── scripts/
│   └── seed.py        # Deterministic fake-data seeder
└── tests/
    ├── conftest.py    # In-memory DB fixture + TestClient
    ├── test_crud.py
    ├── test_filters.py
    ├── test_stats.py
    └── test_health.py
```
