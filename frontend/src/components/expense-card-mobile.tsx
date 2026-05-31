'use client'

import Link from 'next/link'
import { format } from 'date-fns'

import { Card, CardContent } from '@/components/ui/card'
import { buttonVariants } from '@/components/ui/button'
import type { Expense } from '@/types/expense'

interface Props {
  expense: Expense
}

const formatAmount = (amount: number): string =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(amount)

/** Single expense card for mobile list view. */
export function ExpenseCardMobile({ expense }: Props) {
  return (
    <Card>
      <CardContent className="flex flex-col gap-2">
        {/* Top row: date + amount */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            {format(new Date(expense.occurred_at), 'MMM d, yyyy')}
          </span>
          <span className="font-semibold text-sm">{formatAmount(expense.amount)}</span>
        </div>

        {/* Description */}
        <p className="text-sm">{expense.description}</p>

        {/* Bottom row: category badge + edit link */}
        <div className="flex items-center justify-between">
          <span className="text-xs bg-muted px-2 py-0.5 rounded">{expense.category}</span>
          <Link
            href={`/expenses/${expense.id}/edit`}
            className={buttonVariants({ variant: 'ghost', size: 'xs' })}
          >
            Edit
          </Link>
        </div>
      </CardContent>
    </Card>
  )
}
