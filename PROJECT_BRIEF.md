# Project Brief: expense-tracker → shared-household finance app

**Purpose of this document:** full context handoff so a new Claude chat can continue the project without re-deriving history or strategy. Read alongside CURRENT_STATE.md (technical state of the repo) and WORKFLOW.md (the orchestrator process). This brief is the "why and what's planned"; CURRENT_STATE.md is the "what exists technically right now."

---

## 1. What this product is

A personal-finance app that started as a single-user expense tracker and is being extended into an **AI-assisted, UPI-native, shared-household finance app** for the India market. It is live in production.

**Live deployments:**
- Backend (FastAPI on GCP Cloud Run): https://expense-tracker-242393598566.us-central1.run.app
- Frontend (Next.js 16 on Vercel): https://expense-tracker-tawny-eight-98.vercel.app
- GitHub: github.com/gaurav-gandhi-2411/expense-tracker
- GCP project: expense-tracker-498014 (region us-central1)
- Auth + DB: Supabase (Auth with ES256 JWT, Postgres)

**Owner (GG):** ML background, product owner. On Claude Max plan. Works via the orchestrator pattern (see WORKFLOW.md). All projects under `C:\Users\gaura\ml-projects\`. Never set ANTHROPIC_API_KEY (bypasses Max billing).

---

## 2. Build history (phases completed)

| Phase | What shipped |
|---|---|
| v0 | CRUD expense tracker, 8 endpoints, SQLite, stats by month/category |
| Phase 1 | LLM features (Groq): natural-language expense entry, insights narratives — 4 endpoints |
| Phase 2 | Local ML: zero-shot categorization (sentence-transformers), anomaly detection (IsolationForest), forecasting (Prophet) — 4 endpoints |
| Phase 2.5 | Validation + cleanup, eval artifacts |
| Phase 2.6 | ML quality pass: brand-keyword prototypes + LLM fallback → categorizer 8/8 on canonical cases |
| Phase 3a | Production backend: Supabase Auth (dual-algorithm HS256+ES256 JWT), multi-user data isolation, Alembic migrations, Postgres, deployed to Cloud Run |
| Phase 3b | Next.js 16 frontend: auth pages, expense CRUD, NL-input hero, mobile responsive, deployed to Vercel |
| Phase 3b.1 | Auth hardening: fixed sign-in/sign-out bugs (proxy.ts cookie propagation, onSelect→onClick, router cache), added Playwright E2E auth tests |

**Current ML capabilities (all working, carry forward):**
1. Natural-language expense entry ("coffee 180" → structured expense)
2. Insights narratives (monthly + category, LLM-generated)
3. Auto-categorization (zero-shot embeddings + LLM fallback)
4. Anomaly detection (IsolationForest)
5. Spend forecasting (Prophet)

---

## 3. Tech stack

- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2.x (sync), Pydantic v2, Alembic
- **ML:** Groq (LLM — llama-3.3-70b primary, 8b fallback), sentence-transformers, scikit-learn, Prophet
- **Auth/DB:** Supabase (Auth + Postgres); SQLite for local dev/tests
- **Frontend:** Next.js 16 (App Router), TypeScript, Tailwind v4, shadcn/ui (on @base-ui/react), TanStack Query v5, @supabase/ssr
- **Deploy:** Cloud Run (backend, CPU-only torch image), Vercel (frontend)
- **Tests:** pytest (backend, ~143 tests), Playwright (frontend auth E2E)
- **Key gotcha:** Next 16 uses proxy.ts not middleware.ts; async params/searchParams required

---

## 4. The strategic decision (made in prior chat)

GG is building this as **an actual business**, not just a portfolio piece. Goal as GG states it: "replace Splitwise and Walnut in the market and launch mine." The app must serve BOTH individual expense tracking AND group/shared expense splitting in one app, with AI/ML features across both.

**Important honest framing for the new chat to preserve (do not paper over this):**
The market research done in the prior chat showed the India "personal + group + AI expense app" space is already crowded and mature: Walnut/Axio (10M+ users, SMS auto-tracking + splitting + AI), FairShare (AI receipt scanning + UPI deep-link settlement + personal/group, free), and Google Pay (native UPI + group expense features, hundreds of millions of users). There is NO open "first-mover" position for a generic one-stop expense+split app — that was tested and is not available. Competing head-to-head with GPay and Walnut as a generic me-too app would lose.

The new chat should NOT cheerlead "we will replace Walnut and GPay" uncritically. The realistic strategy is to **win a specific underserved niche first** (the wedge below), build it excellently, get real users, and let real usage reveal whether the broader ambition is reachable. The ambition is GG's to hold; the job is to give honest counsel and build the wedge well.

---

## 5. The wedge (the actual near-term strategy)

**"The operating system for shared households" — starting with flatmates/roommates.**

Not episodic dinner-splitting (GPay/Walnut/Splitwise own that). The wedge is the **persistent shared-finance ledger** for flats: rent, electricity, wifi, maid, cook, groceries, gas — the recurring shared costs every urban Indian shared household reconciles monthly via WhatsApp threads and mental math.

Why this wedge:
- **Open position:** incumbents treat splitting as one-off events; nobody owns "the app your flat runs on."
- **High-frequency, recurring pain:** monthly reconciliation, forever, not a once-a-trip annoyance.
- **Sticky / high switching cost:** once a flat's recurring expenses + history + balances live in the app, leaving means rebuilding the ledger. A dinner-splitter has zero switching cost; a household ledger is infrastructure.
- **Leverages everything built:** groups → the flat; splits → household costs; balances + UPI settle-up → monthly reconciliation; existing ML → low-friction NL entry + household insights.
- **Contains both capabilities GG wants:** personal tracking = your own expenses + your slice of shared; "one-stop" satisfied, just *led* by the shared/household angle as the differentiator.
- **Clean expansion path:** flatmates → couples (joint finances) → families → friend groups with ongoing pools → small communities. Household is the beachhead; "persistent shared finances" is the eventual platform.

---

## 6. What carries forward (additive — nothing is being removed)

- All 16 existing backend endpoints
- All 5 ML features (NL entry, insights, categorization, anomaly, forecast) — work on both personal and shared expenses
- Individual expense tracking — preserved as a first-class **Personal tab** (not removed; the home screen leads with the household, but personal tracking is fully intact)
- Full production stack (auth, isolation, Supabase, Cloud Run, Vercel)

The unified data model makes this clean: a personal expense = an expense where you're the only participant; a shared expense = same entity, multiple participants. Same ML pipeline runs over both.

---

## 7. The roadmap (Phase 4 — the new build)

Each is a bounded phase using the orchestrator pattern (spec.md + kickoff). UPI deep-link settlement baked into 4c from the start.

- **4a — Household foundation:** user profiles (display names/avatars beyond raw Supabase UUID), households (groups), memberships, invitations. The social graph. Migrate existing expenses into the unified model. No splitting yet.
- **4b — Shared + recurring expenses + split engine:** payer, participants, split types (equal / exact / percentage / shares), deterministic split calculation. **Recurring expenses (rent, wifi, maid) as a first-class concept** — this is where it beats Splitwise's clunky recurring.
- **4c — Balances + UPI settle-up + monthly reconciliation:** debt-simplification algorithm (minimize transactions), monthly "settle up your flat" flow with one-tap UPI deep-links (`upi://pay?pa=<vpa>&am=<amount>&tn=<note>`), activity feed.
- **4d — AI layer:** NL entry for shared expenses ("electricity 2400 split equally"), **voice entry** (Web Speech API → speech-to-text → existing NL parser; small addition since the parser already exists; makes entry feel effortless and serves the wedge — "split dinner three ways, I paid 1800" by voice), household-level insights/forecasting.
- **4e — Group-first frontend:** home screen = the household (this month's shared expenses, your balance, prominent one-tap "settle up"). Personal tracking = secondary tab. NL input stays hero across both.
- **4f — Mobile:** PWA first (installable, no native rebuild). Native later only if traction.
- **4g — Join-by-link, no forced signup:** flatmates join the household ledger via a WhatsApp link without all creating accounts first (the #1 Splitwise complaint). Designed-for in the 4a invitation model.

---

## 8. Key technical decisions & constraints

- **Unified expense data model:** personal and shared are the same entity (payer + total + set of participant splits). Personal = single participant (you). Build "household" and "recurring expense" as first-class from day one in 4a — these are expensive to retrofit later.
- **Groups-first:** support splitting within named households first; direct friend-to-friend (non-group) splits deferred as a fast-follow. Most real splitting is in groups.
- **Interface re-centers group-first** (see 4e). Not throwing away the current UI — re-orienting the home screen on the flat instead of the individual. That re-centering IS the product differentiation.
- **UPI deep-link settlement:** easy, high-value, no partnership/API approval needed. Build it in 4c. Strongest India feature.
- **SMS-based auto-tracking:** OPT-IN, ANDROID-ONLY (iOS has no SMS-read API AND no notification-read API — capture-by-phone-scraping is permanently Android-only), subject to Google Play restricted-permission review (real hurdle for a new app). Matters LESS for the household wedge (shared expenses are entered deliberately by whoever paid). Stage it LATER.
- **Automatic capture — the real cross-platform path is the RBI Account Aggregator (AA) framework** (consent-based bank/UPI transaction data; works identically on iOS and Android because it's a bank-data pipe, not phone scraping). This is the only way to do "automatic capture" on iOS. It is serious infrastructure, NOT a bolt-on feature: requires registering as a Financial Information User (FIU), integrating an AA (Finvu/Setu/etc.), and consent flows — weeks-to-months plus partnerships. Sequence: voice + NL + manual entry NOW (works everywhere today); AA framework LATER as the real auto-capture play, aimed at the household ("detected you paid the electricity bill — split with your flat?"). Do NOT promise "automatic capture on iOS" before AA is built; it does not exist via any shortcut.
- **Voice entry — YES, build it (in 4d).** Web Speech API captures speech → transcribes → feeds the EXISTING NL parser (the hard part is already built). Small addition, big perceived magic. Serves the wedge (voice-add a shared expense). Works cross-platform in the PWA.
- **Investment tracking — EXPLICITLY OUT OF SCOPE. Do not build it.** It is a different domain (assets growing vs expenses leaving), a different data model, a different UX, and a different competitive set (INDmoney, Groww, Kuvera, Zerodha Coin; Jupiter/Fi racing for the super-app). Adding investments turns this into a "do-everything finance super-app" — the hardest, most capital-intensive thing to build, and exactly where the best-funded players fight. For a solo builder it's a death march. Stay focused on the shared-household wedge.
- **Scope discipline (the most important rule):** every feature must make the SHARED-HOUSEHOLD experience better — that's the position no incumbent owns. The moment a feature is really about "comprehensive personal finance for one person" (auto-capture-everything, investment trends, full personal-finance super-app), the app is competing with Walnut/Jupiter/Fi on their home turf and losing. Personal tracking exists and carries forward, but it is NOT where differentiation or new scope should go. AI/ML is table stakes (every incumbent has it) — focus, not AI, is the edge.

---

## 9. The workflow (how this project is built)

See WORKFLOW.md for full detail. Summary:
- **Orchestrator pattern:** each phase = a spec.md (Claude drafts as downloadable file) + an Opus-4.7 orchestrator kickoff prompt (pasted into a fresh Claude Code session). The orchestrator delegates to `executor` and `verifier` subagents (installed at `C:\Users\gaura\.claude\agents\`).
- **Claude's role (this chat):** strategic planning, writing spec.md files, writing kickoff prompts, reviewing CC output, making decisions at escalation/checkpoint moments.
- **GG's role:** runs CC sessions, relays output back, makes product/business decisions, handles browser/dashboard actions (Supabase, Vercel, GCP) and `/cost` checks that CC can't do.
- **Refinements learned:** (a) cost checks are human-run — orchestrator asks "please run /cost and paste the figure," doesn't try to invoke it; (b) orchestrator must NOT delete/rename files outside spec scope without escalating; (c) when raising a threshold/constant, audit existing tests that use it.

---

## 10. How to start the next chat

1. Share this PROJECT_BRIEF.md + the repo's CURRENT_STATE.md + WORKFLOW.md.
2. Say: "Continue the expense-tracker project. We're starting Phase 4a (household foundation). Write the spec.md and kickoff prompt."
3. The new chat should: confirm understanding of the wedge + current state, then write the Phase 4a spec.md (household data model + profiles + memberships + invitations + migration of existing expenses to the unified model + backend endpoints + tests), then the orchestrator kickoff prompt.
4. Critical for the new chat: design the unified data model (household + recurring expense first-class) carefully in 4a — it's the foundation that's expensive to change later. Spend the design care there.

**Honest note to the next instance of Claude:** GG has heard the competitive reality (Section 4) and chosen to proceed as a business via the household wedge. Keep giving honest counsel — don't re-litigate the decision, but don't pretend "replace GPay/Walnut" is a settled achievable outcome either. Build the wedge excellently; let real usage inform the bigger ambition.
