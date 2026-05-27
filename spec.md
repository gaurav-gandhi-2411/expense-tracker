# Project Spec: expense-tracker — Phase 2.5 (validation + cleanup)

## Goal

Bounded validation + housekeeping iteration between Phase 2 (local ML) and Phase 3 (production deployment). Three deliverables: (1) run the manual ML eval and a live smoke test, capturing both outputs as artifacts; (2) silence the pytest-asyncio deprecation warning; (3) refresh CURRENT_STATE.md to reflect Phase 2 reality. No new features, no new endpoints, no architecture changes.

## Current state (read-only context)
See CURRENT_STATE.md (post-Phase-1 version — known stale; this iteration refreshes it). Key facts:
- Phases v0, 1, 2 are complete: 12 endpoints (8 v0 + 4 Phase 1) + 4 ML endpoints = 16 endpoints
- 103/103 tests pass, ruff + mypy clean
- Phase 2 added: app/ml/ package (embeddings, categorizer, anomaly, forecast), 4 new endpoints, 5 new test files, 5 new config values
- Known cosmetic: pytest-asyncio emits a deprecation warning about `asyncio_default_fixture_loop_scope` being unset

## Scope

### In scope (Phase 2.5)
- Silence the pytest-asyncio deprecation warning by adding `asyncio_default_fixture_loop_scope = "function"` to the `[tool.pytest.ini_options]` section of pyproject.toml
- Create `eval-results/` directory (committed) for capturing eval/smoke artifacts
- Run `python scripts/eval_ml.py` against the REAL embedding model; capture full stdout+stderr to `eval-results/phase2-eval-YYYYMMDD.txt`. If torch/model load fails, escalate with the error.
- Run a live smoke test of the 4 ML endpoints against a locally-running uvicorn:
  - `POST /ml/categorize` with text `"swiggy order 480"` — record response
  - `GET /ml/anomalies?since=2026-01-01` — record response (may be empty; that's fine)
  - `GET /ml/forecast?horizon=2` — record response (likely low-confidence-average mode; that's fine)
  - `POST /ml/train-categorizer` — should refuse (below threshold); record refusal response
  - Capture all four request/response pairs to `eval-results/phase2-smoke-YYYYMMDD.md` as a markdown report
  - Server lifecycle: start uvicorn in background, run requests, stop uvicorn. Use the existing test client if a real-process smoke test is too fragile on Windows — escalate to ask if uncertain.
- Refresh `CURRENT_STATE.md` to reflect Phase 2 reality:
  - Updated directory tree (app/ml/, new test files, eval_ml.py)
  - All 16 endpoints listed
  - app/ml/* modules added to load-bearing list (categorizer + anomaly + forecast)
  - Phase 2 design decisions added (zero-shot-first categorization, thin-data graceful degradation, lazy model loading)
  - Updated test count (103) + lint/types status
  - Updated phase plan (Phase 2 done; Phase 3 next, possibly split into 3a/3b)
  - Add a "Phase 2 eval observations" section summarizing what the eval and smoke test revealed (categorization accuracy on the 8 test cases, any surprises)
- Final commit: all of the above as small, conventionally-named commits

### Out of scope (do NOT do)
- Any new features, endpoints, or ML models
- Any changes to app/ml/* logic — only observe its behavior, don't modify
- Phase 3 work (auth, frontend, deploy, Postgres, Alembic)
- Fixing any categorization errors the eval reveals — RECORD them in CURRENT_STATE.md as observations, do not "improve" the prompts or prototypes
- Caching, performance optimization, retries on smoke calls
- Adding tests (we're just running existing ones, not writing new)
- Cleaning up the dead `# noqa: B008` comments from v0 (separate small task, not this iteration)

## Tech stack additions
None. This iteration uses only what's already installed.

## Architecture (additions only)

```
expense-tracker/
├── eval-results/                          # NEW (committed)
│   ├── phase2-eval-YYYYMMDD.txt           # NEW — eval_ml.py output
│   └── phase2-smoke-YYYYMMDD.md           # NEW — live smoke test report
├── pyproject.toml                          # MODIFIED — pytest-asyncio config
└── CURRENT_STATE.md                       # REWRITTEN — reflect Phase 2
```

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
Run after the pyproject.toml change (verify the deprecation warning is gone in pytest output) and at the end.

## Subagent usage rules
- `executor` for the pyproject.toml edit, eval/smoke runs, and CURRENT_STATE.md rewrite
- `verifier` for the pytest/ruff/mypy verification
- Orchestrator does NOT write content itself

## Escalation rules (orchestrator must ask before doing)
- Ask if torch/embedding model fails to load (could be missing torch install, internet issue for model download, etc.)
- Ask if uvicorn fails to start cleanly for the smoke test
- Ask if any of the 4 smoke-test calls returns an unexpected error (5xx, malformed JSON)
- Ask before modifying anything outside the three files listed in "Architecture additions"
- Ask if any existing test breaks (this iteration shouldn't touch app code — if a test breaks, something's wrong)
- Ask if the smoke test reveals a behavior that contradicts the spec (e.g., train-categorizer succeeds when it should refuse)

## Hard rules (do not violate)
- Do NOT modify any file in app/ — this iteration observes Phase 2 code, doesn't change it
- Do NOT modify any test file
- Do NOT change any endpoint signature or behavior
- Do NOT "fix" categorization errors the eval surfaces — record only
- If the eval reveals broken behavior, STOP and escalate; don't paper over it

## Budget
- Soft target: 30-45 minutes
- Hard cap: 6 executor invocations
- This is a small iteration; if it's getting big, the spec is wrong, not the work

## Success criteria (orchestrator: verify ALL before declaring done)
- pyproject.toml has `asyncio_default_fixture_loop_scope = "function"` and pytest no longer emits the deprecation warning
- `eval-results/phase2-eval-YYYYMMDD.txt` exists, contains the full eval_ml.py output, and shows per-test-case results for the 8 categorization cases
- `eval-results/phase2-smoke-YYYYMMDD.md` exists with the 4 endpoint request/response pairs, each clearly labeled
- CURRENT_STATE.md is rewritten to reflect Phase 2 reality (16 endpoints, app/ml/ package, 103 tests, updated load-bearing list, design decisions, phase plan)
- CURRENT_STATE.md has a new "Phase 2 eval observations" section with concrete observations from the eval + smoke artifacts
- 103/103 tests still pass, ruff + mypy still clean
- Final commit log shows small, conventionally-named commits — one per logical change

## Build order
1. pyproject.toml: add `asyncio_default_fixture_loop_scope = "function"` under `[tool.pytest.ini_options]`. Run pytest, confirm warning is gone, commit.
2. Create eval-results/ directory (add a .gitkeep or README so it's tracked).
3. Run `python scripts/eval_ml.py`, capture output to eval-results/phase2-eval-<today>.txt. Commit.
4. Run live smoke test of 4 ML endpoints. Capture to eval-results/phase2-smoke-<today>.md. Commit.
5. Rewrite CURRENT_STATE.md to reflect Phase 2 reality + add "Phase 2 eval observations" section drawing from the artifacts from steps 3-4. Commit.
6. Final verification pass — all checks green, success criteria walkthrough.
