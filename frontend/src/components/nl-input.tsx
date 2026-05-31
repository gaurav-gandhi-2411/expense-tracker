'use client'

import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { useCreateFromText } from '@/lib/hooks/use-expenses'

interface NLInputProps {
  onSuccess?: () => void
}

export function NLInput({ onSuccess }: NLInputProps) {
  const [text, setText] = useState('')
  const createFromText = useCreateFromText()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!text.trim()) return
    try {
      await createFromText.mutateAsync({ text: text.trim() })
      toast.success('Expense added!')
      setText('')
      onSuccess?.()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to add expense'
      toast.error(message)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <textarea
        className="w-full rounded-md border border-input bg-background px-3 py-2 text-base ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring min-h-[100px] resize-none"
        placeholder='Try: "lunch with team ₹450" or "Uber to airport 1200"'
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={createFromText.isPending}
      />
      <Button
        type="submit"
        disabled={!text.trim() || createFromText.isPending}
        className="w-full sm:w-auto"
      >
        {createFromText.isPending ? 'Parsing & adding…' : 'Parse & Add'}
      </Button>
    </form>
  )
}
