'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { buttonVariants } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { ExpenseForm } from '@/components/expense-form'
import { NLInput } from '@/components/nl-input'
import { useCreateExpense } from '@/lib/hooks/use-expenses'
import type { ExpenseCreate } from '@/types/expense'

export default function NewExpensePage() {
  const router = useRouter()
  const [showManual, setShowManual] = useState(false)
  const createExpense = useCreateExpense()

  async function handleManualSubmit(values: ExpenseCreate) {
    await createExpense.mutateAsync(values)
    toast.success('Expense added!')
    router.push('/expenses')
  }

  return (
    <div className="max-w-xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Add expense</h1>
        <Link href="/expenses" className={buttonVariants({ variant: 'ghost', size: 'sm' })}>
          Cancel
        </Link>
      </div>

      {/* Hero: Natural language input */}
      <Card>
        <CardHeader>
          <CardTitle>Describe your expense</CardTitle>
          <CardDescription>
            Type naturally — amount, description, and date will be parsed automatically.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <NLInput onSuccess={() => router.push('/expenses')} />
        </CardContent>
      </Card>

      <Separator />

      {/* Secondary: Manual form */}
      <div>
        <Button
          variant="ghost"
          className="flex items-center gap-1 text-sm text-muted-foreground px-0"
          onClick={() => setShowManual((v) => !v)}
        >
          {showManual ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
          Add manually
        </Button>

        {showManual && (
          <div className="mt-4">
            <ExpenseForm
              submitLabel="Add expense"
              onSubmit={handleManualSubmit}
              isLoading={createExpense.isPending}
            />
          </div>
        )}
      </div>
    </div>
  )
}
