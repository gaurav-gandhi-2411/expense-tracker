# Project Spec: expense-tracker

## Goal

A personal expense tracker as a FastAPI service backed by SQLite. Single-user, runs locally, no auth. Provides CRUD endpoints for expenses, plus a few aggregation endpoints (total by month, total by category). This is the v0 test target for the loop orchestrator — small enough to finish end-to-end in one session, real enough to expose how the orchestrator handles a multi-step build.

## Scope

### In scope (v0)
- SQLite database with one table: `expenses` (id, amount, category, description, occurred_at, created_at)
- Pydantic v2 schemas for create / update / read
- FastAPI app with these endpoints:
  - `POST   /expenses`        — create
  - `GET    /expenses`        — list, supports `?category=` and `?since=YYYY-MM-DD` query params
  - `GET    /expenses/{id}`   — get one
  - `PATCH  /expenses/{id}`   — partial update
  - `DELETE /expenses/{id}`   — delete
  - `GET    /stats/by-month`  — returns `[{month: "2026-01", total: 1234.56}, ...]`
  - `GET    /stats/by-category` — returns `[{category: "food", total: 567.89}, ...]`
  - `GET    /health`          — returns `{"status": "ok"}`
- A CLI seed script (`scripts/seed.py`) that inserts 20-30 realistic fake expenses across the last 3 months for manual testing
- pytest test suite with at least one test per endpoint, using FastAPI's `TestClient` and an in-memory SQLite for tests
- `README.md` with: install, run, seed, manual curl examples for each endpoint

### Out of scope (do not build)
- Authentication / multi-user support
- Frontend or web UI
- Docker, deployment, CI/CD
- Migrations framework (Alembic) — schema is created at startup via SQLAlchemy `metadata.create_all`
- Receipt uploads, file storage, image processing
- Budgets, alerts, recurring expenses, currency conversion
- Async DB driver — use synchronous SQLAlchemy for simplicity
- Logging framework — `print` is fine for v0
- Pagination on list endpoint — return all matches

## Tech stack

- Python 3.11+
- FastAPI
- SQLAlchemy 2.x (sync, not async)
- Pydantic v2
- uvicorn (server)
- pytest, httpx (for TestClient)
- ruff (lint), mypy (types)

Install with `pip` into a `.venv`. No uv, no poetry — keep it boring.

## Architecture

```
expense-tracker/
├── pyproject.toml
├── README.md
├── .venv/                          (gitignored)
├── expense_tracker.db              (gitignored, created at runtime)
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI app + routes
│   ├── db.py                       # SQLAlchemy engine + session factory
│   ├── models.py                   # SQLAlchemy ORM models
│   ├── schemas.py                  # Pydantic request/response schemas
│   └── stats.py                    # Aggregation queries (by-month, by-category)
├── scripts/
│   └── seed.py
└── tests/
    ├── __init__.py
    ├── conftest.py                 # in-memory db fixture, TestClient fixture
    ├── test_crud.py                # one test per CRUD endpoint
    ├── test_filters.py             # ?category= and ?since= filters
    ├── test_stats.py               # by-month + by-category
    └── test_health.py
```

## Data model

```python
class Expense(Base):
    id: int           # primary key, autoincrement
    amount: float     # in rupees (single currency for v0)
    category: str     # free-form string, e.g. "food", "transport"
    description: str  # short note, can be empty string
    occurred_at: date # the date the expense happened (not the row creation time)
    created_at: datetime  # row creation timestamp, server default = now()
```

Index on `(occurred_at)` and `(category)` for the stats queries.

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
  required: false  # warnings ok in v0, fail-state not blocking
```

Run all three after every executor pass.

## Subagent usage rules

- Use the `executor` subagent for any pass that writes or edits files
- Use the `verifier` subagent for running tests / lint / types
- The orchestrator (main session) reads this spec, plans the next pass, delegates, and decides "next pass | escalate | done"
- The orchestrator does NOT write code itself — delegate to executor every time

## Escalation rules (orchestrator must ask before doing)

- Ask before installing any dependency not listed in "Tech stack"
- Ask before adding any new top-level directory or top-level file beyond what's in "Architecture"
- Ask if a single executor pass would touch more than 8 files
- Ask if verification fails 3 times in a row on the same check despite executor retries
- Ask if the executor reports the assigned task is bigger than its scope description suggested

When escalating, state the question clearly and wait for the user's response before proceeding.

## Budget

- Soft target: complete v0 in 1 CC session
- Hard cap: stop and escalate if cumulative work exceeds 20 executor invocations without "done"
- Stop and ask if `/cost` (run it occasionally) reports more than the user's stated comfort threshold

## Success criteria (orchestrator: verify ALL of these before declaring done)

- All 8 endpoints implemented and reachable
- `pytest -v` reports all tests pass, with at least one test per endpoint
- `ruff check .` reports no errors
- `python -m uvicorn app.main:app` starts cleanly with no errors
- `python scripts/seed.py` populates the database without errors
- After seeding, `curl localhost:8000/stats/by-month` returns non-empty JSON
- `README.md` exists and contains: install steps, run command, seed command, one example curl per endpoint
- No files outside the structure defined in "Architecture"

## Build order (recommended sequence; orchestrator may adjust)

1. Project scaffolding: pyproject.toml, .gitignore, .venv setup, install deps, blank module files
2. db.py + models.py (Expense ORM + engine + session factory)
3. schemas.py (Pydantic create/update/read)
4. main.py with health endpoint only; verify it starts
5. CRUD endpoints (POST, GET list, GET by id, PATCH, DELETE) — with filter query params
6. stats.py + the two stats endpoints
7. tests/conftest.py + test_health.py — verify test infrastructure works
8. Remaining test files (test_crud, test_filters, test_stats)
9. scripts/seed.py
10. README.md
11. Final verification pass — all checks green, manual curl smoke test
