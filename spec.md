# Project Spec: expense-tracker — Phase 3b.1 (auth flow hardening + E2E tests)

## Goal

Sign-in and sign-out are not working reliably on the deployed app. This iteration: (1) diagnose the actual auth flow bug(s), (2) pull Playwright forward from Phase 3c to add automated E2E tests covering auth scenarios, (3) fix the bugs, (4) prove the full auth flow works locally across multiple scenarios. Human validates on Vercel only after local E2E passes green.

The auth experience must be smooth and regression-protected before any further frontend work.

## Current state (read-only context)
See CURRENT_STATE.md. Key facts:
- Frontend: Next.js 16 (App Router), @supabase/ssr for auth, proxy.ts (NOT middleware.ts) for route protection, TanStack Query for data
- Backend live on Cloud Run; dual-algorithm JWT auth; CORS allows the Vercel prod URL + localhost:3000
- Known-good: backend health, CORS config, NEXT_PUBLIC_API_BASE_URL now set in Vercel (data calls fixed in prior session)
- A manually-created, auto-confirmed Supabase test user exists (e.g. smoke3@expense-tracker.local)
- Supabase email sign-up is rate-limited on free tier — auth testing must use PRE-CREATED users + sign-IN, never programmatic sign-up

## Symptom (to reproduce and diagnose)
"Sign in and sign out not working properly." Specifics unknown — the orchestrator must reproduce and characterize the exact failure before fixing. Common Next 16 + @supabase/ssr + proxy.ts failure modes to investigate:
- Session cookie not refreshed/persisted by proxy.ts (logged out on reload)
- Sign-out clears client state but not server cookies (still "logged in" after)
- Redirect logic reading stale session state (flash of wrong page, or no redirect)
- Browser vs server Supabase client created in the wrong context
- Cookie sameSite/secure/domain misconfiguration
- proxy.ts matcher not covering the right routes

## Scope

### In scope (Phase 3b.1)
**Diagnosis**
- Read the auth implementation: proxy.ts, the Supabase client factories (lib/supabase/client.ts + server.ts), sign-in page handler, sign-out action, the authenticated layout's auth gate
- Identify the specific defect(s) causing unreliable sign-in/sign-out
- Report the root cause with evidence before fixing

**Playwright setup (pulled forward from Phase 3c)**
- Install Playwright in frontend/ (@playwright/test + browser binaries)
- `frontend/playwright.config.ts` — configured to start the dev server (or test against an already-running one), Chromium project, baseURL http://localhost:3000
- Test credentials via a gitignored `frontend/.env.test.local` (TEST_USER_EMAIL, TEST_USER_PASSWORD); committed `.env.test.local.example` template
- npm script `test:e2e` → `playwright test`
- gitignore: add `frontend/.env.test.local`, `frontend/test-results/`, `frontend/playwright-report/`

**E2E auth tests (`frontend/e2e/auth.spec.ts`)** — cover these scenarios:
1. Sign in with valid credentials → redirects to /expenses, user is authenticated
2. Sign in with invalid credentials → error message shown, stays on /sign-in
3. Sign in with empty/invalid fields → client validation error, no submit
4. Session persists across page reload → reload /expenses while signed in stays on /expenses (does NOT bounce to /sign-in)
5. Sign out → redirects to /sign-in AND session is actually cleared
6. After sign out, direct-navigate to /expenses → redirects to /sign-in (cookie truly gone)
7. Direct-navigate to /expenses while logged out → redirects to /sign-in
8. Direct-navigate to /sign-in while logged in → redirects to /expenses
9. (if applicable) Rapid sign-in → sign-out → sign-in does not leave stale session

**Bug fixes**
- Fix the auth defect(s) found in diagnosis so all 9 scenarios pass
- Fixes likely live in proxy.ts (session refresh), the sign-out handler (proper supabase.auth.signOut() + cookie clearing + redirect), and/or the Supabase server client cookie wiring
- Keep changes minimal and targeted — this is hardening, not a rewrite

### Out of scope (Phase 3c or later)
- E2E tests for expense CRUD (separate, Phase 3c)
- Component/unit tests (Vitest, React Testing Library)
- CI integration (GitHub Actions)
- Testing the sign-UP form flow (email rate-limited; use pre-created users)
- Password reset, email confirmation, social auth
- Any non-auth feature work
- Production/Vercel testing by the orchestrator (human does that)
- Visual regression testing

## Tech stack additions (frontend)
- @playwright/test
- (Playwright browser binaries via `npx playwright install chromium`)

No other deps. If the orchestrator wants more, escalate.

## Architecture (additions + likely modifications)
```
frontend/
├── playwright.config.ts            # NEW
├── .env.test.local                 # NEW (gitignored) — test user creds
├── .env.test.local.example         # NEW (committed)
├── e2e/
│   └── auth.spec.ts                # NEW — 9 auth scenarios
├── package.json                    # MODIFIED — test:e2e script, @playwright/test dep
├── proxy.ts                        # LIKELY MODIFIED — session refresh fix
└── src/
    ├── lib/supabase/
    │   ├── client.ts               # POSSIBLY MODIFIED
    │   └── server.ts               # POSSIBLY MODIFIED
    ├── app/sign-in/                # POSSIBLY MODIFIED — handler/error display
    └── components/                 # POSSIBLY MODIFIED — sign-out action
```

## Verification commands
```yaml
- name: e2e-auth
  cmd: cd frontend && npx playwright test
  required: true
- name: type-check
  cmd: cd frontend && npx tsc --noEmit
  required: true
- name: lint
  cmd: cd frontend && npx next lint
  required: true
- name: build
  cmd: cd frontend && npm run build
  required: true
- name: backend-tests
  cmd: pytest -v
  required: true  # must not regress
```

## Subagent usage rules
- `executor` for all code/config writes
- `verifier` for running Playwright, type-check, lint, build, backend tests
- Orchestrator does NOT write code

## Interactive checkpoints (human action — only where CC cannot proceed)
**Checkpoint A — test credentials (required before E2E can run):**
The orchestrator cannot know a Supabase user's password. It pauses and asks the human to:
1. Confirm an auto-confirmed test user exists in Supabase (or create one via dashboard: Authentication → Users → Add user → Auto Confirm)
2. Create `frontend/.env.test.local` with:
   TEST_USER_EMAIL=<the test user email>
   TEST_USER_PASSWORD=<that user's password>
3. Confirm back that the file exists (without pasting the password into chat)

**Checkpoint B — Vercel validation (after local E2E green):**
Once all 9 scenarios pass locally, the human manually validates sign-in/sign-out on the live Vercel URL (https://expense-tracker-tawny-eight-98.vercel.app), since the orchestrator cannot see the live browser. If a bug only manifests in production (e.g. cookie secure/sameSite differences over HTTPS), human reports it and the orchestrator fixes.

## Escalation rules
- Ask before installing any dep beyond @playwright/test
- Ask if Playwright browser install fails (large download; network/proxy issues possible on Windows)
- Ask if any backend test regresses (this iteration should not touch backend)
- Ask if the auth bug appears to require a change to the backend auth (it should not — backend auth is verified working)
- Ask if a fix would change the Supabase client public API used elsewhere
- Ask if reproducing the bug requires the live Vercel environment (i.e. can't repro locally) — then it's a Checkpoint B finding

## Hard rules
- Do NOT touch backend code (app/, tests/, migrations/)
- Do NOT test or fix the sign-UP form (email-rate-limited; out of scope)
- Do NOT commit .env.test.local or any password
- Do NOT make the auth fix a rewrite — minimal, targeted changes only
- Use proxy.ts (Next 16), never create middleware.ts
- Use the current @supabase/ssr cookie pattern (createBrowserClient / createServerClient), not deprecated auth-helpers

## Budget
- Soft target: 60-90 minutes
- Hard cap: 14 executor invocations
- Playwright browser download is a one-time cost; not counted against pace

## Success criteria (orchestrator: verify ALL before declaring done)
- Root cause of the sign-in/sign-out issue identified and documented
- Playwright installed and configured; `npx playwright test` runs
- All 9 auth E2E scenarios pass locally, green
- The specific bug(s) fixed with minimal, targeted changes
- type-check clean, lint clean, build succeeds
- Backend tests still pass (no regression)
- .env.test.local gitignored; .env.test.local.example committed
- A short writeup of the root cause + fix added to CURRENT_STATE.md (or a new eval-results/phase3b1-auth-fix-YYYYMMDD.md artifact)
- Human has validated the fix on the live Vercel URL (Checkpoint B) — sign-in, reload-persists, sign-out, re-sign-in all smooth

## Build order
1. Diagnose: read proxy.ts, lib/supabase/client.ts + server.ts, sign-in handler, sign-out action, authenticated layout. State the suspected root cause(s) with evidence. **(no fix yet)**
2. Install Playwright + browser binaries. Create playwright.config.ts, .env.test.local.example, gitignore entries, test:e2e script. **[CHECKPOINT A: human provides test creds]**
3. Write e2e/auth.spec.ts with all 9 scenarios. Run against the current (buggy) code to CONFIRM the tests actually catch the reported failures — at least one scenario should fail, reproducing the bug. Report which scenarios fail.
4. Fix the auth defect(s). Re-run E2E until all 9 pass. Keep changes minimal.
5. Full verification: E2E green, type-check, lint, build, backend tests. Write the root-cause + fix summary artifact.
6. **[CHECKPOINT B: human validates on Vercel]** — report instructions for the human to test the live flow. If production-only issues surface, fix and re-verify.
7. Final success-criteria walkthrough.
