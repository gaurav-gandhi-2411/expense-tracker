'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'

import { Button, buttonVariants } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { ExpenseForm } from '@/components/expense-form'
import {
  useDeleteExpense,
  useExpense,
  useUpdateExpense,
} from '@/lib/hooks/use-expenses'
import type { ExpenseCreate } from '@/types/expense'

interface Props {
  id: number
}

export function EditExpenseClient({ id }: Props) {
  const router = useRouter()
  const { data: expense, isLoading, isError } = useExpense(id)
  const updateExpense = useUpdateExpense()
  const deleteExpense = useDeleteExpense()

  async function handleSave(values: ExpenseCreate) {
    await updateExpense.mutateAsync({ id, data: values })
    toast.success('Expense updated!')
    router.push('/expenses')
  }

  async function handleDelete() {
    await deleteExpense.mutateAsync(id)
    toast.success('Expense deleted.')
    router.push('/expenses')
  }

  if (isLoading) {
    return (
      <div className="max-w-xl mx-auto space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    )
  }

  if (isError || !expense) {
    return (
      <div className="max-w-xl mx-auto text-center py-12">
        <p className="text-muted-foreground">Failed to load expense.</p>
        <Link href="/expenses" className={buttonVariants({ variant: 'ghost', size: 'sm' })}>
          Back to list
        </Link>
      </div>
    )
  }

  const deleteButton = (
    <Dialog>
      <DialogTrigger
        render={
          <Button variant="destructive" type="button">
            Delete
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete expense?</DialogTitle>
          <DialogDescription>
            This will permanently delete &ldquo;{expense.description}&rdquo;. This action cannot be
            undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            variant="destructive"
            onClick={handleDelete}
            disabled={deleteExpense.isPending}
          >
            {deleteExpense.isPending ? 'Deleting…' : 'Delete'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )

  return (
    <div className="max-w-xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Edit expense</h1>
        <Link href="/expenses" className={buttonVariants({ variant: 'ghost', size: 'sm' })}>
          Cancel
        </Link>
      </div>

      <ExpenseForm
        defaultValues={{
          description: expense.description,
          amount: expense.amount,
          category: expense.category,
          occurred_at: expense.occurred_at.split('T')[0],
        }}
        onSubmit={handleSave}
        submitLabel="Save changes"
        isLoading={updateExpense.isPending}
        extraActions={deleteButton}
      />
    </div>
  )
}
