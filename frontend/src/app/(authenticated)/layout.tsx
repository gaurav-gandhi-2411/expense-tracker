import { redirect } from 'next/navigation'

import { createClient } from '@/lib/supabase/server'
import { Nav } from '@/components/nav'

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
      <Nav email={user.email ?? ''} />
      <main className="flex-1 container mx-auto px-4 py-6">{children}</main>
    </div>
  )
}
