export interface Expense {
  id: number
  description: string
  amount: number
  category: string
  occurred_at: string
  user_id: string
  created_at: string
  updated_at: string | null
}

export interface ExpenseCreate {
  description: string
  amount: number
  category?: string
  occurred_at?: string
}

export interface ExpenseUpdate {
  description?: string
  amount?: number
  category?: string
  occurred_at?: string
}

export interface TextInput {
  text: string
}

export interface ParsedExpense {
  description: string
  amount: number
  category: string
  occurred_at: string
}
