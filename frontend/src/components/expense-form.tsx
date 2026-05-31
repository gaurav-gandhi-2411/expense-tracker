'use client'

import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import type { ExpenseCreate } from '@/types/expense'

const expenseSchema = z.object({
  description: z.string().min(1, 'Description is required'),
  // HTML number inputs deliver a string to RHF; accept string|number and coerce
  amount: z
    .union([z.string(), z.number()])
    .transform((val) => (typeof val === 'string' ? parseFloat(val) : val))
    .refine((val) => !isNaN(val) && val > 0, 'Amount must be positive'),
  category: z.string().optional(),
  occurred_at: z.string().optional(),
})

// Input type (raw form values) — amount comes from HTML input as string|number
type ExpenseFormInput = z.input<typeof expenseSchema>
// Output type (parsed/validated values) — amount is always number after transform
type ExpenseFormValues = z.output<typeof expenseSchema>

interface ExpenseFormProps {
  defaultValues?: Partial<ExpenseFormInput>
  onSubmit: (values: ExpenseCreate) => Promise<void>
  submitLabel?: string
  isLoading?: boolean
  extraActions?: React.ReactNode
}

export function ExpenseForm({
  defaultValues,
  onSubmit,
  submitLabel = 'Save',
  isLoading,
  extraActions,
}: ExpenseFormProps) {
  const form = useForm<ExpenseFormInput, unknown, ExpenseFormValues>({
    resolver: zodResolver(expenseSchema),
    defaultValues: {
      description: '',
      amount: 0,
      category: '',
      occurred_at: new Date().toISOString().split('T')[0],
      ...defaultValues,
    },
  })

  async function handleSubmit(values: ExpenseFormValues): Promise<void> {
    await onSubmit({
      description: values.description,
      amount: values.amount,
      category: values.category || undefined,
      occurred_at: values.occurred_at
        ? new Date(values.occurred_at).toISOString()
        : undefined,
    })
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Description</FormLabel>
              <FormControl>
                <Input placeholder="e.g., Lunch at Zomato" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="amount"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Amount (₹)</FormLabel>
              <FormControl>
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  placeholder="0.00"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="category"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Category (optional)</FormLabel>
              <FormControl>
                <Input placeholder="e.g., Food, Transport" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="occurred_at"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Date</FormLabel>
              <FormControl>
                <Input type="date" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <div className="flex items-center gap-3 pt-2">
          <Button type="submit" disabled={form.formState.isSubmitting || isLoading}>
            {form.formState.isSubmitting ? 'Saving…' : submitLabel}
          </Button>
          {extraActions}
        </div>
      </form>
    </Form>
  )
}
