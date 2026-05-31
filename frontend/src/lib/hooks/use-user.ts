'use client'

import { useEffect, useState } from 'react'

import type { User } from '@supabase/supabase-js'

import { createClient } from '@/lib/supabase/client'

export function useUser() {
  const [user, setUser] = useState<User | null>(null)

  useEffect(() => {
    const supabase = createClient()

    supabase.auth.getUser().then(({ data: { user } }) => setUser(user))

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null)
    })

    return () => subscription.unsubscribe()
  }, [])

  return user
}
