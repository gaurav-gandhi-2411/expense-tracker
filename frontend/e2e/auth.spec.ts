import { test, expect, type Page } from '@playwright/test'

const TEST_EMAIL = process.env.TEST_USER_EMAIL!
const TEST_PASSWORD = process.env.TEST_USER_PASSWORD!

if (!TEST_EMAIL || !TEST_PASSWORD) {
  throw new Error(
    'TEST_USER_EMAIL and TEST_USER_PASSWORD must be set in frontend/.env.test.local'
  )
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function signIn(page: Page, email = TEST_EMAIL, password = TEST_PASSWORD) {
  await page.goto('/sign-in')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.waitForURL(/\/expenses/, { timeout: 15_000 })
}

async function signOut(page: Page) {
  // Desktop nav: click the dropdown trigger (button whose text is the email)
  // then click the "Sign out" menu item
  await page.getByRole('button', { name: TEST_EMAIL }).click()
  await page.getByRole('menuitem', { name: 'Sign out' }).click()
  await page.waitForURL(/\/sign-in/, { timeout: 15_000 })
}

// ---------------------------------------------------------------------------
// Test suite
// ---------------------------------------------------------------------------

test.describe('Auth flow', () => {
  // Scenario 1 — valid sign-in navigates to /expenses and user is authenticated
  test('1 · valid credentials → /expenses, user authenticated', async ({ page }) => {
    await page.goto('/sign-in')
    await page.getByLabel('Email').fill(TEST_EMAIL)
    await page.getByLabel('Password').fill(TEST_PASSWORD)
    await page.getByRole('button', { name: 'Sign in' }).click()

    await expect(page).toHaveURL(/\/expenses/, { timeout: 15_000 })
    // The nav shows the email — confirms the server rendered the authenticated layout
    await expect(page.getByRole('button', { name: TEST_EMAIL })).toBeVisible()
  })

  // Scenario 2 — invalid password shows error toast, stays on /sign-in
  test('2 · invalid credentials → error message, stays on /sign-in', async ({ page }) => {
    await page.goto('/sign-in')
    await page.getByLabel('Email').fill(TEST_EMAIL)
    await page.getByLabel('Password').fill('wrong-password-xyzzy')
    await page.getByRole('button', { name: 'Sign in' }).click()

    await expect(page).toHaveURL(/\/sign-in/, { timeout: 10_000 })
    // Supabase returns "Invalid login credentials"; sonner toast shows error.message
    await expect(page.getByText(/invalid login credentials/i)).toBeVisible({ timeout: 10_000 })
  })

  // Scenario 3 — empty email fails client-side Zod validation, no submit
  test('3 · empty fields → client validation error, no network request', async ({ page }) => {
    await page.goto('/sign-in')
    // Click submit without filling anything
    await page.getByRole('button', { name: 'Sign in' }).click()

    await expect(page).toHaveURL(/\/sign-in/)
    // react-hook-form / zod shows "Please enter a valid email" inline
    await expect(page.getByText(/valid email/i)).toBeVisible({ timeout: 5_000 })
  })

  // Scenario 4 — session persists across a hard page reload
  test('4 · session persists across page reload', async ({ page }) => {
    await signIn(page)
    await page.reload()

    await expect(page).toHaveURL(/\/expenses/, { timeout: 15_000 })
    await expect(page.getByRole('button', { name: TEST_EMAIL })).toBeVisible()
  })

  // Scenario 5 — sign-out redirects to /sign-in AND session is actually cleared
  test('5 · sign out → /sign-in, session cleared', async ({ page }) => {
    await signIn(page)
    await signOut(page)

    await expect(page).toHaveURL(/\/sign-in/)
    // The email button (authenticated nav) must NOT be visible
    await expect(page.getByRole('button', { name: TEST_EMAIL })).not.toBeVisible()
  })

  // Scenario 6 — after sign-out, direct navigation to /expenses bounces back to /sign-in
  test('6 · after sign out, /expenses → /sign-in redirect', async ({ page }) => {
    await signIn(page)
    await signOut(page)
    await page.goto('/expenses')

    await expect(page).toHaveURL(/\/sign-in/, { timeout: 15_000 })
  })

  // Scenario 7 — unauthenticated direct navigation to /expenses redirects to /sign-in
  test('7 · unauthenticated /expenses → /sign-in redirect', async ({ page }) => {
    // Fresh context — no cookies
    await page.goto('/expenses')

    await expect(page).toHaveURL(/\/sign-in/, { timeout: 15_000 })
  })

  // Scenario 8 — authenticated user navigating to /sign-in is redirected to /expenses
  test('8 · authenticated /sign-in → /expenses redirect', async ({ page }) => {
    await signIn(page)
    await page.goto('/sign-in')

    await expect(page).toHaveURL(/\/expenses/, { timeout: 15_000 })
  })

  // Scenario 9 — rapid sign-in → sign-out → sign-in leaves no stale session
  test('9 · rapid sign-in → sign-out → sign-in, no stale session', async ({ page }) => {
    await signIn(page)
    await signOut(page)
    await signIn(page)  // second sign-in

    await expect(page).toHaveURL(/\/expenses/, { timeout: 15_000 })
    await expect(page.getByRole('button', { name: TEST_EMAIL })).toBeVisible()
  })
})
