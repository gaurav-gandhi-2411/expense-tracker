'use client'

import Link from 'next/link'
import { format } from 'date-fns'
import { Plus } from 'lucide-react'

import { useExpenses } from '@/lib/hooks/use-expenses'
import { Button, buttonVariants } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { ExpenseCardMobile } from '@/components/expense-card-mobile'
import type { Expense } from '@/types/expense'

const formatAmount = (amount: number): string =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(amount)

const formatDate = (dateStr: string): string =>
  format(new Date(dateStr), 'MMM d, yyyy')

export default function ExpensesPage() {
  const { data, isLoading, isError, refetch } = useExpenses()

  return (
    <div>
      {/* Page header — always shown */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Expenses</h1>
        <Link href="/expenses/new" className={buttonVariants({ size: 'sm' })}>
          <Plus className="h-4 w-4 mr-1" /> Add expense
        </Link>
      </div>

      {/* Loading state */}
      {isLoading && (
        <>
          {/* Desktop skeletons */}
          <div className="hidden md:block">
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="flex gap-4">
                  <Skeleton className="h-8 w-32" />
                  <Skeleton className="h-8 w-32" />
                  <Skeleton className="h-8 flex-1" />
                </div>
              ))}
            </div>
          </div>
          {/* Mobile skeletons */}
          <div className="md:hidden space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-24 w-full" />
            ))}
          </div>
        </>
      )}

      {/* Error state */}
      {isError && !isLoading && (
        <div className="flex flex-col items-center justify-center gap-4 py-12">
          <p className="text-muted-foreground">Failed to load expenses.</p>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            Try again
          </Button>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !isError && data?.length === 0 && (
        <div className="flex flex-col items-center justify-center gap-4 py-12">
          <p className="text-muted-foreground">No expenses yet — add your first</p>
          <Link href="/expenses/new" className={buttonVariants({ size: 'sm' })}>
            Add expense
          </Link>
        </div>
      )}

      {/* Populated state */}
      {!isLoading && !isError && data && data.length > 0 && (
        <>
          {/* Desktop table */}
          <Table className="hidden md:table">
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Amount</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((expense: Expense) => (
                <TableRow key={expense.id}>
                  <TableCell>{formatDate(expense.occurred_at)}</TableCell>
                  <TableCell>{expense.category}</TableCell>
                  <TableCell>{expense.description}</TableCell>
                  <TableCell>{formatAmount(expense.amount)}</TableCell>
                  <TableCell>
                    <Link
                      href={`/expenses/${expense.id}/edit`}
                      className={buttonVariants({ variant: 'ghost', size: 'sm' })}
                    >
                      Edit
                    </Link>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          {/* Mobile cards */}
          <div className="md:hidden space-y-3">
            {data.map((expense: Expense) => (
              <ExpenseCardMobile key={expense.id} expense={expense} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}
