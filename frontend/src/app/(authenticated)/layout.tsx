import { redirect } from 'next/navigation'

import { createClient } from '@/lib/supabase/server'

export default async function AuthenticatedLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const supabase = await createClient()
  const {
    data: { user },
  } = await supabase.auth.getUser()

  if (!user) {
    redirect('/sign-in')
  }

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b px-4 py-3 flex items-center justify-between">
        <span className="font-semibold text-lg">Expense Tracker</span>
        <span className="text-sm text-muted-foreground">{user.email}</span>
      </header>
      <main className="flex-1">{children}</main>
    </div>
  )
}
