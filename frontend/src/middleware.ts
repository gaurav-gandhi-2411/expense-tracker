import { NextResponse, type NextRequest } from 'next/server'

// Staged, not active: this only changes behavior once MAINTENANCE_MODE=true is set as a
// Vercel env var and a new deployment picks it up. Merging this file alone changes nothing
// in production -- deliberate two-step gate (env var + deploy) since GG must decide when
// this goes live, not this branch.
//
// Why this exists: the backend (Cloud Run) has been returning 503 on every request since
// billing was disabled on expensetracker-prod-260814, but sign-in itself is handled by
// Supabase Auth directly (see src/app/page.tsx / src/app/sign-in), not the backend -- so a
// visitor sees a fully working-looking sign-in page and only discovers the product is dead
// after trying to actually use it. This middleware, once enabled, replaces that misleading
// experience with an honest one.
export function middleware(request: NextRequest) {
  if (process.env.MAINTENANCE_MODE !== 'true') {
    return NextResponse.next()
  }

  const { pathname } = request.nextUrl
  if (pathname === '/maintenance' || pathname.startsWith('/_next') || pathname === '/favicon.ico') {
    return NextResponse.next()
  }

  return NextResponse.redirect(new URL('/maintenance', request.url))
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
}
