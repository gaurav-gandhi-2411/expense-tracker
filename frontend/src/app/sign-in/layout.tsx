import { redirect } from 'next/navigation'

import { createClient } from '@/lib/supabase/server'

export default async function SignInLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const supabase = await createClient()
  const {
    data: { user },
  } = await supabase.auth.getUser()

  if (user) {
    redirect('/expenses')
  }

  return <>{children}</>
}
