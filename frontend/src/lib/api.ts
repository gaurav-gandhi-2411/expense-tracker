import { createClient } from '@/lib/supabase/client'

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL!

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function getToken(): Promise<string> {
  const supabase = createClient()
  const {
    data: { session },
  } = await supabase.auth.getSession()
  if (!session?.access_token) throw new ApiError(401, 'Not authenticated')
  return session.access_token
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = await getToken()
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...(options.headers as Record<string, string>),
    },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(res.status, (body as { detail?: string }).detail ?? res.statusText)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}
