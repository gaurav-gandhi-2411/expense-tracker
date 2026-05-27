# Project Spec: expense-tracker — Phase 2.6 (ML quality pass)

## Goal

Address the concrete ML quality issues surfaced by Phase 2.5's eval. Three targeted improvements driven by recorded observations: (1) expand zero-shot category prototypes to include common Indian brand keywords (Swiggy, Zomato, Ola, Rapido, etc.); (2) add an LLM-fallback path in the categorizer when zero-shot confidence is low; (3) tune anomaly detection to be less noisy and gate the endpoint below a minimum sample threshold. Re-run eval + smoke and document the before/after.

NO new endpoints. NO new features. Tightly scoped quality work driven by data.

## Current state (read-only context)
See CURRENT_STATE.md (post-Phase-2.5). Phase 2.5 eval recorded:
- Categorizer 6/8 (75%) on curated cases — "uber to office" → rent (should be transport), "netflix" → entertainment (got "subscription" — prototype collision)
- Live smoke: "swiggy order 480" → utilities at score 0.19 — out-of-vocabulary brand
- Anomaly flag rate 42% on N=26 seeded data — too noisy to be useful
- Prophet ran on 4 months (above 3-month threshold) — correct behavior, output not actionable yet

This iteration fixes #1, #2, and #3. The Prophet thin-data limitation is data-bound, not addressable in code; left as-is.

Load-bearing files (per CURRENT_STATE.md): app/db.py, app/models.py, tests/conftest.py, app/llm.py, app/config.py.

## Scope

### In scope (Phase 2.6)
**Categorizer prototype expansion:**
- Expand the built-in category prototype map in `app/ml/categorizer.py` so each category's prototype text includes representative brand keywords. Target categories and example expansions:
  - `food`: include "swiggy zomato dunzo restaurant cafe meal lunch dinner"
  - `transport`: include "ola uber rapido auto taxi metro bmtc cab fuel petrol"
  - `groceries`: include "bigbasket blinkit zepto instamart grocery supermarket"
  - `utilities`: include "electricity water gas internet wifi broadband bill recharge jio airtel"
  - `entertainment`: include "netflix prime hotstar spotify movies concert streaming"
  - `health`: include "medicine pharmacy hospital doctor clinic medical apollo"
  - `rent`: include "rent housing flat apartment monthly accommodation"
  - `other`: include "miscellaneous"
- Remove "subscription" as a top-level category prototype if present — it was colliding with entertainment on netflix and similar
- Prototypes are still embedded once at startup (no behavior change beyond the keyword set)

**LLM fallback in categorizer:**
- New function `extract_category(text: str) -> str` in `app/parser.py` — does a category-only LLM call using the existing Groq client. Lighter prompt than full `parse_expense_text`; returns just the category string.
- Modify `suggest_category(text)` in `app/ml/categorizer.py`:
  - Run zero-shot first as today
  - If best score < `CATEGORIZER_FALLBACK_THRESHOLD` (new config, default 0.30), call `extract_category(text)` and return its result
  - `CategorySuggestion.mode` gains a new value `"llm-fallback"` for this path
  - If the LLM call fails (rate limit, etc.), return the zero-shot result with a `confidence_note` indicating fallback was attempted and failed

**Anomaly tuning:**
- Lower `IsolationForest(contamination=...)` default from 0.10 to 0.05 in `app/ml/anomaly.py`
- Raise `MIN_ANOMALY_SAMPLES` default from 20 to 50 in `app/config.py`
- The endpoint `GET /ml/anomalies` already returns empty + note below threshold (per Phase 2 spec) — no endpoint changes, just the threshold value

**New tests:**
- `tests/test_categorizer.py` — add: (a) LLM-fallback path with mocked LLM (assert mode = "llm-fallback"); (b) LLM-fallback failure path (assert graceful degradation to zero-shot result + note); (c) prototype-expansion sanity check (food prototype embedding now contains keyword "swiggy" — assert the constant string)
- `tests/test_anomaly.py` — add: (a) below-threshold-50 returns empty + note (existing test was at N<20); (b) above-threshold N=60 still flags injected outlier
- `tests/test_parser.py` — add tests for `extract_category` (mocked Groq client, 4-5 inputs from the original 8 eval cases)

**Re-run eval + smoke (artifacts):**
- Run `python scripts/eval_ml.py` against the updated categorizer. Capture to `eval-results/phase2-eval-v2-YYYYMMDD.txt`
- Run live smoke of `POST /ml/categorize` for: `"swiggy order 480"`, `"uber to office 240"`, `"netflix 649"`. Capture to `eval-results/phase2-smoke-v2-YYYYMMDD.md`
- For each result, the smoke report must show: input text, suggested category, score, mode (zero-shot or llm-fallback)
- Brief side-by-side comparison vs Phase 2.5 results inside the smoke markdown file

**CURRENT_STATE.md update:**
- Update "Phase 2 eval observations" section into "Phase 2 eval observations (v1)" and add "Phase 2.6 eval observations (v2)" with the before/after comparison
- Update test count
- Note the LLM-fallback addition in design decisions

### Out of scope (do NOT do)
- Any Phase 3 work (auth, frontend, deploy, Postgres, Alembic)
- Changing the embedding model (no swap from all-MiniLM-L6-v2)
- Re-engineering anomaly or forecast beyond the two tunings specified
- LLM response caching, retries beyond what app/llm.py already has
- New endpoints
- Touching app/llm.py public surface (load-bearing)
- Improving category prototypes beyond the keyword expansion (no fancy multi-token mean pooling, no learned prototypes)
- Cleaning up unrelated lint or noqa comments

## Tech stack additions
None. Uses existing Groq client (app/llm.py) via app/parser.py.

## Architecture (modifications only)

```
expense-tracker/
├── app/
│   ├── ml/
│   │   ├── categorizer.py     # MODIFIED — expanded prototypes, LLM fallback wiring, new mode value
│   │   └── anomaly.py         # MODIFIED — contamination 0.10 → 0.05
│   ├── parser.py              # MODIFIED — new extract_category(text) function
│   ├── schemas.py             # MODIFIED — CategorySuggestion.mode gains "llm-fallback" value; optional confidence_note field
│   └── config.py              # MODIFIED — CATEGORIZER_FALLBACK_THRESHOLD (new), MIN_ANOMALY_SAMPLES (20 → 50)
├── tests/
│   ├── test_categorizer.py    # MODIFIED — 3 new tests
│   ├── test_anomaly.py        # MODIFIED — 2 new tests
│   └── test_parser.py         # MODIFIED — extract_category tests
├── eval-results/
│   ├── phase2-eval-v2-YYYYMMDD.txt   # NEW
│   └── phase2-smoke-v2-YYYYMMDD.md   # NEW
└── CURRENT_STATE.md           # MODIFIED — v2 observations section
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

## Subagent usage rules
- `executor` for all code changes, eval/smoke runs, CURRENT_STATE.md update
- `verifier` for tests/lint/types
- Orchestrator does NOT write code

## Escalation rules (orchestrator must ask before doing)
- Ask before modifying any load-bearing file (CURRENT_STATE.md list)
- Ask if eval_ml.py output looks substantially WORSE than v1 — that means we broke something
- Ask if any existing test from the 103 baseline starts failing
- Ask if torch fails to load when running eval (network/model-cache issue)
- Ask if uvicorn smoke test is fragile on Windows — fallback to TestClient is acceptable if discussed
- Ask if the LLM-fallback path causes test flakiness or rate-limit errors during the live smoke

## Hard rules (do not violate)
- Do NOT modify app/llm.py
- Do NOT modify app/db.py, app/models.py, tests/conftest.py
- Do NOT change any endpoint signature or behavior
- Do NOT remove or rename any file
- Do NOT make real LLM calls inside pytest — mock the Groq client
- Do NOT swap the embedding model
- Do NOT touch Prophet or forecast code

## Budget
- Soft target: 60-75 minutes
- Hard cap: 10 executor invocations
- Per-pass token budget: spec is tight enough that no single pass should exceed 25k

## Success criteria (orchestrator: verify ALL before declaring done)
- All 103 baseline tests still pass
- 6 new tests added (3 categorizer, 2 anomaly, 1+ parser) — actual count may be slightly higher but ≥6
- `pytest -v` reports 109+ tests, 0 fail
- `ruff check .` clean, `mypy app` clean
- New eval artifact at `eval-results/phase2-eval-v2-YYYYMMDD.txt` shows categorizer results on the 8 curated cases
- New smoke artifact at `eval-results/phase2-smoke-v2-YYYYMMDD.md` shows the three live inputs (swiggy/uber/netflix) with category + score + mode for each, plus a before/after comparison vs v1
- **Quantitative improvement targets** (not hard fails, but flag if missed):
  - "uber to office 240" → transport (was rent)
  - "netflix 649" → entertainment (was subscription)
  - "swiggy order 480" → food (was utilities) — may require LLM fallback to land correctly; that's the design intent
- CURRENT_STATE.md updated with v2 observations section + test count + design decisions
- All commits trailer-free, conventionally named, one logical change per commit

## Build order
1. app/config.py: add CATEGORIZER_FALLBACK_THRESHOLD (default 0.30), bump MIN_ANOMALY_SAMPLES (20 → 50). Verify tests still pass.
2. app/parser.py: add `extract_category(text: str) -> str` with mocked-LLM test. Verify.
3. app/ml/anomaly.py: lower contamination to 0.05. Add test for new threshold gate. Verify.
4. app/ml/categorizer.py: expand prototype keywords, remove "subscription" if present, add LLM-fallback wiring (read threshold from config, call extract_category, set mode). Update CategorySuggestion schema for new mode value + optional note. Add 3 new tests. Verify.
5. Run eval + smoke against real model and live server. Capture artifacts to eval-results/. Commit.
6. Update CURRENT_STATE.md with v2 observations (read artifact text; do not generalize). Final verification pass.
