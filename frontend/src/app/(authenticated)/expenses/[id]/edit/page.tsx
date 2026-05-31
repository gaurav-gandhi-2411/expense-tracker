import { EditExpenseClient } from '../edit-client'

interface PageProps {
  params: Promise<{ id: string }>
}

export default async function EditExpensePage({ params }: PageProps) {
  const { id } = await params
  return <EditExpenseClient id={parseInt(id, 10)} />
}
