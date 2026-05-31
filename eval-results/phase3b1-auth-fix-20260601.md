# Phase 3b.1 Auth Fix — 2026-06-01

## Root causes identified

### Bug 1 (CRITICAL — scenarios 5, 6, 9): `onSelect` is not a valid prop on @base-ui/react `Menu.Item`
`nav.tsx` used `onSelect={handleSignOut}` on `DropdownMenuItem`. The shadcn/ui
`DropdownMenuItem` wraps `@base-ui/react`'s `MenuPrimitive.Item`, which has no
`onSelect` prop (that is a Radix UI convention). The prop was silently treated
as an unknown HTML attribute, so `handleSignOut` was never called. The dropdown
closed on click but no navigation or sign-out occurred.

**Fix**: `onSelect` → `onClick` on the sign-out `DropdownMenuItem` in `nav.tsx`.

### Bug 2 (MODERATE — scenario 8): proxy.ts redirect for authenticated users on `/sign-in` unreliable in dev
`proxy.ts` correctly redirects unauthenticated users from `/expenses` to
`/sign-in`, but the reverse redirect (authenticated user on `/sign-in` →
`/expenses`) was not reliably firing in the local dev environment. Root cause
not definitively pinned, but likely a timing or cookie-visibility difference
between the proxy's `createServerClient` and the downstream server component
context.

**Fix**: Added `src/app/sign-in/layout.tsx` — an async server component that
calls `supabase.auth.getUser()` via the server client (which reads from the
request cookie store already refreshed by proxy.ts's `getUser()` run) and
redirects authenticated users to `/expenses`. This is the same pattern already
used by `(authenticated)/layout.tsx` for the inverse check.

### Bug 3 (LATENT — production token-refresh reliability): proxy.ts redirect responses discarded refreshed tokens
Both redirect branches in `proxy.ts` returned raw `NextResponse.redirect(url)`
objects, discarding the `supabaseResponse` that contains any auth cookies
refreshed during `supabase.auth.getUser()`. When Supabase rotates a near-expiry
access token during a request that ends in a redirect, the new token was never
sent to the browser. The browser continued with the old token; when it expired
the session was silently lost.

**Fix**: Both redirect branches now create a `redirectResponse`, copy
`supabaseResponse.cookies` onto it, and return that. Fresh-token cases are
unaffected (supabaseResponse.cookies is empty; the forEach is a no-op).

### Bug 4 (MINOR — sign-in/out navigation): `router.push + router.refresh` ordering
`sign-in/page.tsx` and `nav.tsx` both used `router.push(destination)` then
`router.refresh()`. In Next.js 16 App Router, this soft-navigation pattern does
not reliably propagate Supabase session cookies through proxy.ts's HTTP cookie
machinery on the next full request.

**Fix**: Replaced with `window.location.assign(destination)` (sign-in) and
`window.location.href = destination` (sign-out). Both cause a full HTTP
navigation through proxy.ts, which validates the session and sets correct
response cookies.

## Files changed

| File | Change |
|---|---|
| `frontend/proxy.ts` | Both redirect branches propagate `supabaseResponse` cookies |
| `frontend/src/app/sign-in/page.tsx` | `window.location.assign('/expenses')` after sign-in |
| `frontend/src/app/sign-in/layout.tsx` | NEW — server component auth guard for `/sign-in` |
| `frontend/src/components/nav.tsx` | `onSelect` → `onClick`; `window.location.href` for sign-out |
| `frontend/playwright.config.ts` | NEW — Playwright config |
| `frontend/e2e/auth.spec.ts` | NEW — 9 auth E2E scenarios |
| `frontend/.env.test.local.example` | NEW — test credentials template |
| `frontend/package.json` | Added `test:e2e` script; `@playwright/test` devDep |
| `.gitignore` | Added Playwright output dirs and `.env.test.local` |

## E2E results (all local, Chromium)

| # | Scenario | Result |
|---|----------|--------|
| 1 | valid credentials → /expenses, user authenticated | PASS |
| 2 | invalid credentials → error message, stays on /sign-in | PASS |
| 3 | empty fields → client validation error, no network request | PASS |
| 4 | session persists across page reload | PASS |
| 5 | sign out → /sign-in, session cleared | PASS |
| 6 | after sign out, /expenses → /sign-in redirect | PASS |
| 7 | unauthenticated /expenses → /sign-in redirect | PASS |
| 8 | authenticated /sign-in → /expenses redirect | PASS |
| 9 | rapid sign-in → sign-out → sign-in, no stale session | PASS |

type-check: clean · lint: clean · build: succeeds · backend tests: 143/143
