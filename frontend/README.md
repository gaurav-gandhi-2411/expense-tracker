# Expense Tracker — Frontend

Next.js 16 frontend for the Expense Tracker API. Connects to the live Cloud Run backend at https://expense-tracker-242393598566.us-central1.run.app.

## Stack

- Next.js 16 (App Router) + React 19 + TypeScript
- Tailwind CSS v4 + shadcn/ui (@base-ui/react primitives)
- @supabase/ssr — session-safe Supabase auth
- TanStack Query v5 — server state
- react-hook-form + zod v4 — form validation
- date-fns v4 — date formatting

## Local development

### 1. Install dependencies

```bash
npm install
```

### 2. Set up environment variables

Copy `.env.local.example` to `.env.local` and fill in your Supabase project values:

```bash
cp .env.local.example .env.local
```

| Variable | Where to find it |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project → Settings → API → Project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase project → Settings → API → Project API keys → anon public |
| `NEXT_PUBLIC_API_BASE_URL` | Your Cloud Run service URL |

### 3. Run the dev server

```bash
npm run dev
```

Open http://localhost:3000. Sign up with any email/password to get started.

## Auth flow

- `proxy.ts` (Next.js 16 route proxy) protects `/expenses/*` — unauthenticated users are redirected to `/sign-in`
- Supabase session is stored in cookies via `@supabase/ssr`
- JWT is read from the session and sent as `Authorization: Bearer <token>` to all API calls

## Project structure

```
src/
├── app/
│   ├── layout.tsx              # Root layout — React Query provider + Toaster
│   ├── page.tsx                # Root redirect (→ /expenses or /sign-in)
│   ├── sign-in/page.tsx        # Email/password sign-in
│   ├── sign-up/page.tsx        # Registration
│   └── (authenticated)/        # Route group — auth-gated layout + nav
│       ├── layout.tsx
│       └── expenses/
│           ├── page.tsx        # Expense list (desktop table + mobile cards)
│           ├── new/page.tsx    # Add expense (NL input hero + manual form)
│           └── [id]/edit/      # Edit/delete expense
├── components/
│   ├── ui/                     # shadcn/ui components
│   ├── nav.tsx                 # Top nav (desktop + mobile hamburger)
│   ├── expense-card-mobile.tsx # Mobile expense card
│   ├── expense-form.tsx        # Shared add/edit form
│   ├── nl-input.tsx            # Natural-language input hero
│   └── providers.tsx           # React Query provider
├── lib/
│   ├── supabase/               # Browser + server Supabase clients
│   ├── api.ts                  # Fetch wrapper (adds JWT, throws ApiError)
│   └── hooks/                  # React Query hooks (useExpenses, etc.)
└── types/
    └── expense.ts              # TypeScript types mirroring backend schemas
```

## Deploy to Vercel

1. Go to vercel.com/new → Import the `expense-tracker` repo from GitHub
2. Set **Root Directory** to `frontend`
3. Framework Preset: Next.js (auto-detected)
4. Add Environment Variables (Production + Preview):
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `NEXT_PUBLIC_API_BASE_URL` = `https://expense-tracker-242393598566.us-central1.run.app`
5. Click Deploy

After the first deploy, update your Cloud Run service's `CORS_ALLOWED_ORIGINS` to include the Vercel production URL.
