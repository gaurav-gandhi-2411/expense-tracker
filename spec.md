# Project Spec: expense-tracker — Phase 3b (frontend foundation + auth + CRUD + deploy)

## Goal

Build a Next.js 15 frontend on top of the live Cloud Run backend. Ship a minimum viable product: users sign up via Supabase Auth, log in, add expenses (natural-language input as the hero interaction), view their expenses, edit, delete. Mobile-responsive throughout. Deploy to Vercel free tier. At the end of Phase 3b, the product is usable by a friend with a sign-up link — fully end-to-end.

ML feature demos (categorize tester, anomalies, forecast) and insights/charts are OUT OF SCOPE (Phase 3c).

## Current state (read-only context)
See CURRENT_STATE.md (post-Phase-3a). Key facts:
- Backend live at https://expense-tracker-242393598566.us-central1.run.app
- Supabase project active; ES256 JWT signing (dual-algorithm validator in app/auth.py handles both ES256 and HS256)
- 141/141 backend tests pass, ruff + mypy clean
- 16 backend endpoints, all require JWT except /health
- User-scoped data isolation verified end-to-end (test_isolation.py + live e2e artifact)
- Test user `test@expense-tracker.local` exists in Supabase Auth
- All Phase 1/2/2.6 features working live

This iteration adds the `frontend/` directory at repo root alongside existing `app/`, `tests/`, etc. No backend code changes EXCEPT a CORS allowlist update.

## Scope

### In scope (Phase 3b)

**Project scaffolding**
- New `frontend/` directory at repo root
- Next.js 15.x with App Router, TypeScript (strict mode), Tailwind CSS, ESLint
- shadcn/ui initialized (`components.json` configured)
- Install minimum shadcn components needed: button, input, label, card, form, dialog, dropdown-menu, toast, separator, skeleton, table
- TanStack Query (@tanstack/react-query) for server state
- Supabase JS client (@supabase/supabase-js)
- @supabase/ssr for Next.js App Router integration
- lucide-react (comes with shadcn) for icons
- date-fns for date formatting (lightweight)

**Auth (Supabase via custom shadcn forms)**
- `/sign-in` page — email + password form, "Sign in" button, link to /sign-up
- `/sign-up` page — email + password form, "Create account" button, link to /sign-in
- Form validation via react-hook-form + zod (shadcn standard)
- Both forms use shadcn Form + Input + Button components
- Auth calls go through Supabase JS client; session stored via @supabase/ssr (cookies, SSR-safe)
- Auth state available via a `useUser()` hook
- Middleware (`middleware.ts`) protects authenticated routes — unauthenticated users hitting protected paths redirect to /sign-in
- Sign-out action in the nav

**API client layer**
- `frontend/src/lib/api.ts` — fetch wrapper that:
  - Reads JWT from current Supabase session
  - Adds `Authorization: Bearer <token>` to all requests
  - Reads base URL from `NEXT_PUBLIC_API_BASE_URL` env var
  - Throws typed errors on non-2xx (so React Query handles them cleanly)
- TypeScript types in `frontend/src/types/expense.ts` mirroring the backend's Pydantic schemas — Expense, ExpenseCreate, ExpenseUpdate, ParsedExpense, TextInput
- React Query hooks in `frontend/src/lib/hooks/`:
  - `useExpenses()` — list with optional filters
  - `useExpense(id)` — single
  - `useCreateExpense()`, `useCreateFromText()`, `useUpdateExpense()`, `useDeleteExpense()` mutations
  - Mutations invalidate the list query on success

**Pages (5 screens)**
- `/` (root) — redirects to /expenses if signed in, /sign-in if not
- `/sign-in` and `/sign-up` (already covered above)
- `/expenses` (list view, authenticated)
  - Desktop: table with columns: occurred_at, category, description, amount, actions
  - Mobile: stacked cards
  - Empty state ("No expenses yet — add your first")
  - Loading skeleton while fetching
  - Error state with retry button
- `/expenses/new` (add view, authenticated)
  - HERO: large natural-language input (textarea + "Parse & Add" button) — uses POST /expenses/from-text
  - SECONDARY: collapsible "Add manually" form below — uses POST /expenses
  - On success: toast notification, redirect to /expenses
  - On error: toast with error detail
- `/expenses/[id]/edit` (edit view, authenticated)
  - Pre-filled form with all fields
  - Save (PATCH) + Delete (with confirm dialog) + Cancel
  - On save/delete: toast + redirect to /expenses

**Layout & navigation**
- Authenticated routes share a layout with a top nav bar
- Nav contents: app name/logo (text is fine), "Expenses" link, "Add expense" button, user email + sign-out menu
- Desktop: horizontal nav bar
- Mobile: hamburger menu (sheet/drawer) opening from the left

**Mobile responsiveness (must work cleanly)**
- All pages tested mentally at 360px wide
- Touch targets ≥44px (Tailwind's default sizing on buttons/inputs satisfies this)
- Tables → cards transition at md: breakpoint
- Forms stack vertically on small screens
- Nav collapses to hamburger below md:

**Backend update (single env var change, no code change)**
- After Vercel preview/prod URLs are known, update Cloud Run's `CORS_ALLOWED_ORIGINS` env var to include them
- Specifically: `https://<your-vercel-prod>.vercel.app` + `https://<your-vercel-preview>.vercel.app` + `http://localhost:3000`
- Done via `gcloud run services update` — no redeploy from source needed
- Orchestrator generates the exact command; human runs it at the interactive checkpoint

**Environment variables (frontend)**
- `NEXT_PUBLIC_SUPABASE_URL` (same as backend's SUPABASE_URL)
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` (the anon/public key from Supabase Settings → API)
- `NEXT_PUBLIC_API_BASE_URL` (https://expense-tracker-242393598566.us-central1.run.app)
- `.env.local.example` committed with placeholders; `.env.local` in .gitignore
- Same three vars set in Vercel project's Environment Variables settings (Production + Preview)

**README updates (in `frontend/README.md`)**
- "Local development" — npm install, env vars, npm run dev
- "Deploy to Vercel" — the manual steps the human did
- Project structure overview

**CURRENT_STATE.md refresh (in repo root, the backend's CURRENT_STATE.md)**
- Update to reflect Phase 3a auth.py changes (dual-algorithm, audience claim)
- Add Phase 3b section: frontend repo structure, Vercel URL, env vars, Phase 3c plan

### Out of scope (Phase 3c — do NOT build now)
- Insights view (monthly + category narratives)
- Stats charts (recharts integration, by-month, by-category visualizations)
- ML feature demos: categorize tester UI, anomalies view, forecast view
- Component tests (Vitest, React Testing Library)
- E2E tests (Playwright)
- Dark mode
- User profile / settings page
- Password reset, email confirmation flows
- Social auth (Google, GitHub OAuth)
- Advanced filters/search/pagination
- CSV export
- Internationalization (i18n)
- Storybook
- CI for the frontend (no GitHub Actions in 3b)
- Custom domain on Vercel

## Tech stack additions (frontend only — none for backend in this iteration)

Frontend:
- next@15.x
- react@19.x
- typescript@5.x
- tailwindcss@4.x
- @tanstack/react-query@5.x
- @supabase/supabase-js@2.x
- @supabase/ssr@latest
- react-hook-form@7.x
- zod@3.x
- date-fns@3.x
- lucide-react (transitive via shadcn)
- shadcn/ui components (installed individually via CLI)
- eslint, prettier, prettier-plugin-tailwindcss

If executor wants others, escalate.

## Architecture (additions only)

```
expense-tracker/
├── app/                                # UNCHANGED (backend)
├── tests/                              # UNCHANGED (backend)
├── migrations/                         # UNCHANGED
├── frontend/                           # NEW (entire directory)
│   ├── package.json
│   ├── next.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── postcss.config.mjs
│   ├── components.json                 # shadcn config
│   ├── .env.local                      # gitignored
│   ├── .env.local.example
│   ├── README.md
│   ├── middleware.ts                   # auth protection
│   ├── public/
│   │   └── favicon.ico
│   └── src/
│       ├── app/
│       │   ├── layout.tsx              # root layout + React Query provider
│       │   ├── globals.css             # Tailwind base + shadcn vars
│       │   ├── page.tsx                # root redirect
│       │   ├── sign-in/page.tsx
│       │   ├── sign-up/page.tsx
│       │   └── (authenticated)/        # route group
│       │       ├── layout.tsx          # nav + auth gate
│       │       └── expenses/
│       │           ├── page.tsx        # list
│       │           ├── new/page.tsx    # add
│       │           └── [id]/edit/page.tsx
│       ├── components/
│       │   ├── ui/                     # shadcn components live here
│       │   ├── nav.tsx
│       │   ├── nav-mobile.tsx
│       │   ├── expense-list.tsx
│       │   ├── expense-card-mobile.tsx
│       │   ├── expense-form.tsx
│       │   ├── nl-input.tsx            # hero NL input component
│       │   └── providers.tsx           # React Query provider
│       ├── lib/
│       │   ├── supabase/
│       │   │   ├── client.ts           # browser client
│       │   │   └── server.ts           # server client (cookies)
│       │   ├── api.ts                  # fetch wrapper with JWT
│       │   ├── hooks/
│       │   │   └── use-expenses.ts     # React Query hooks
│       │   └── utils.ts                # cn() helper from shadcn
│       └── types/
│           └── expense.ts
├── CURRENT_STATE.md                    # MODIFIED — refreshed for Phase 3a + 3b
└── (backend files unchanged)
```

## Verification commands (frontend)

Frontend doesn't have a pytest equivalent in scope, so verification is build + lint + type check:

```yaml
- name: type-check
  cmd: cd frontend && npx tsc --noEmit
  required: true
- name: lint
  cmd: cd frontend && npx next lint
  required: true
- name: build
  cmd: cd frontend && npm run build
  required: true
```

Backend verification (must still pass — no regression allowed):
```yaml
- name: backend-tests
  cmd: pytest -v
  required: true
- name: backend-lint
  cmd: ruff check .
  required: true
- name: backend-types
  cmd: mypy app
  required: false
```

## Subagent usage rules
- `executor` for all frontend file writes
- `verifier` for tests/lint/types/build
- Orchestrator does NOT write code

## Interactive checkpoints

**Checkpoint A — after step 1 (CURRENT_STATE refresh):** Human confirms the refreshed CURRENT_STATE.md accurately captures Phase 3a state. Replies "approved" or with concerns.

**Checkpoint B — after step 4 (Supabase client + auth pages working locally):** Human runs `cd frontend && npm run dev` and manually tests:
1. Visit http://localhost:3000 → redirects to /sign-in
2. Sign up with a new test email (e.g. ph3b-test@expense-tracker.local) and password
3. After sign-up, redirect to /expenses (empty list)
4. Sign out → back to /sign-in
5. Sign in with the same credentials → back to /expenses
Human pastes back: "auth flow works" or specific errors with screenshots/console output.

**Checkpoint C — after step 8 (all CRUD pages working locally):** Human runs the dev server and tests the full CRUD loop end-to-end at localhost:3000. Specifically:
1. Add expense via natural-language input: "lunch 250"
2. Verify it appears in the list
3. Click edit → change amount → save → verify in list
4. Click delete → confirm → verify gone from list
Human reports back: "CRUD works" or issues.

**Checkpoint D — Vercel project setup (human action):**
Orchestrator pauses with instructions:
1. Go to vercel.com/new
2. Import the expense-tracker repo from GitHub
3. Configure project:
   - Root Directory: `frontend`
   - Framework Preset: Next.js (auto-detected)
   - Build/Output settings: defaults
4. Environment Variables (Production + Preview):
   - `NEXT_PUBLIC_SUPABASE_URL` = (paste from .env)
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY` = (paste from .env)
   - `NEXT_PUBLIC_API_BASE_URL` = `https://expense-tracker-242393598566.us-central1.run.app`
5. Deploy
6. Paste back the production URL (format: `https://<project-name>.vercel.app`)

**Checkpoint E — CORS update on Cloud Run (orchestrator runs gcloud directly):**
Once Vercel URL is known, orchestrator runs:
```
gcloud run services update expense-tracker --region us-central1 --update-env-vars "CORS_ALLOWED_ORIGINS=https://<vercel-url>,http://localhost:3000"
```

**Checkpoint F — Live e2e smoke (human-driven, orchestrator-guided):**
Human opens the production Vercel URL in a browser, runs through the full flow (sign up, add expense via NL, edit, delete, sign out). Reports any failures with browser console output. Orchestrator captures the result to `eval-results/phase3b-frontend-smoke-YYYYMMDD.md`.

## Escalation rules
- Ask before installing any frontend dependency beyond those listed
- Ask if Next.js version detected isn't 15.x
- Ask if any backend test starts failing (this iteration should not touch backend code)
- Ask if Vercel build fails
- Ask if Supabase auth flow fails after Checkpoint B
- Ask if any CRUD operation fails after Checkpoint C
- Ask if CORS blocks the deployed frontend from reaching the backend
- Ask if React Query/Supabase SSR setup produces hydration warnings

## Hard rules
- Do NOT modify any backend code (`app/`, `tests/`, `migrations/`, root pyproject.toml, etc.)
- The CORS update is the ONLY backend change permitted, and only via `gcloud run services update` (env var only — no code/deploy)
- Do NOT commit any frontend `.env.local` file
- Do NOT commit Supabase anon key into source (only into .env.local.example as a placeholder)
- Do NOT add any feature listed in "Out of scope" speculatively
- Do NOT use Pages Router — App Router only
- Do NOT use any deprecated Next.js APIs (no `getServerSideProps`, no `getStaticProps`)
- Do NOT install jest, vitest, playwright, cypress — testing is Phase 3c

## Budget
- Soft target: 120-150 minutes
- Hard cap: 18 executor invocations
- Cost-equivalent estimate: $14-22
- /cost checkpoints after step 4 (auth working locally) and after Checkpoint E (CORS updated, ready for live smoke)

## Success criteria (orchestrator: verify ALL before declaring done)
- Backend tests still 141/141 pass; ruff clean; mypy clean (no backend regression)
- `cd frontend && npm run build` succeeds with no errors
- `cd frontend && npx tsc --noEmit` clean
- `cd frontend && npx next lint` clean
- Locally: sign-up, sign-in, sign-out flow works (Checkpoint B passed)
- Locally: full CRUD loop works (Checkpoint C passed)
- Vercel production deploy live, URL reachable
- Live e2e flow on the Vercel URL works end-to-end (Checkpoint F captured to eval artifact)
- Mobile responsive verified on at least one screen size (Chrome devtools mobile emulation; capture screenshot or note in the smoke artifact)
- CURRENT_STATE.md refreshed: Phase 3a + 3b state captured, frontend URL noted, Phase 3c plan outlined
- frontend/README.md exists with local dev + deploy steps
- All commits trailer-free, conventionally named, one logical change per commit (likely 8-12 commits)
- `eval-results/phase3b-frontend-smoke-YYYYMMDD.md` exists

## Build order
1. **Refresh CURRENT_STATE.md** first — capture Phase 3a state (dual-algo auth, deployed URL, etc.) BEFORE starting frontend work. **[CHECKPOINT A]**
2. Initialize Next.js 15 in `frontend/`: `npx create-next-app@latest frontend --typescript --tailwind --app --eslint --src-dir --import-alias "@/*"`. Add to root .gitignore: `frontend/.env.local`, `frontend/node_modules`, `frontend/.next`.
3. Install shadcn/ui (`npx shadcn@latest init`) + components listed in spec. Install Supabase JS + ssr + React Query + react-hook-form + zod + date-fns.
4. Build Supabase client (lib/supabase/), API client (lib/api.ts), TypeScript types (types/expense.ts), providers (components/providers.tsx). Wire React Query provider into root layout. Build sign-in + sign-up pages with shadcn forms. Build middleware.ts for route protection. Build the (authenticated) route group layout with a placeholder nav. Test locally. **[CHECKPOINT B + cost check]**
5. Build the nav component (desktop + mobile hamburger variants). Wire sign-out action.
6. Build expense list page (`/expenses`): desktop table + mobile cards, loading/empty/error states.
7. Build add expense page (`/expenses/new`): NL input as hero, manual form as collapsible secondary. Wire mutations.
8. Build edit expense page (`/expenses/[id]/edit`): pre-filled form, save + delete with confirm dialog. **[CHECKPOINT C]**
9. Final local verification: build clean, type-check clean, lint clean. README.md in frontend/. Push to GitHub.
10. **[CHECKPOINT D]** Vercel setup (human creates project, sets env vars, deploys, returns URL).
11. **[CHECKPOINT E]** CORS update on Cloud Run via gcloud (orchestrator runs).
12. **[CHECKPOINT F + cost check]** Live smoke test on the Vercel URL (human-driven, orchestrator-guided). Capture artifact.
13. Update CURRENT_STATE.md with deployed Vercel URL and Phase 3c plan. Final success-criteria walkthrough.
