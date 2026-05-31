'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api'
import type {
  Expense,
  ExpenseCreate,
  ExpenseUpdate,
  TextInput,
} from '@/types/expense'

export function useExpenses() {
  return useQuery({
    queryKey: ['expenses'],
    queryFn: () => apiFetch<Expense[]>('/expenses'),
  })
}

export function useExpense(id: number) {
  return useQuery({
    queryKey: ['expenses', id],
    queryFn: () => apiFetch<Expense>(`/expenses/${id}`),
    enabled: !!id,
  })
}

export function useCreateExpense() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: ExpenseCreate) =>
      apiFetch<Expense>('/expenses', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['expenses'] }),
  })
}

export function useCreateFromText() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: TextInput) =>
      apiFetch<Expense>('/expenses/from-text', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['expenses'] }),
  })
}

export function useUpdateExpense() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ExpenseUpdate }) =>
      apiFetch<Expense>(`/expenses/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['expenses'] }),
  })
}

export function useDeleteExpense() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<void>(`/expenses/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['expenses'] }),
  })
}
