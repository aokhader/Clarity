import { ApiError } from '@/api/client'
import type { ChatBudgetOut } from '@/api/types'

/** What the composers say once the day's chat spend is used up (rule 6 of the chat contract). */
export const BUDGET_SPENT = 'Today’s chat budget is spent; it resets at midnight.'

/** Whether the server refused a question because the day's chat spend is used up. */
export function isBudgetRefusal(error: unknown): boolean {
  return error instanceof ApiError && error.status === 429
}

/** Whether today's chat spend has reached its cap, by the server's own figures. */
export function budgetSpent(budget: ChatBudgetOut | undefined): boolean {
  return budget !== undefined && budget.spent_today_micro_usd >= budget.cap_micro_usd
}

/** Past this share of the cap, the composers show what is spent. */
const BUDGET_WARN_NUMERATOR = 4
const BUDGET_WARN_DENOMINATOR = 5

/** More than four fifths of the cap spent: worth a line by the Ask button. */
export function budgetNearlySpent(budget: ChatBudgetOut | undefined): boolean {
  return (
    budget !== undefined &&
    budget.spent_today_micro_usd * BUDGET_WARN_DENOMINATOR > budget.cap_micro_usd * BUDGET_WARN_NUMERATOR
  )
}

/** A refused question or retry, in a sentence that says what to do. */
export function askErrorText(error: Error): string {
  if (!(error instanceof ApiError)) return `The question could not be sent. ${error.message}`
  switch (error.status) {
    case 429:
      return BUDGET_SPENT
    case 409:
      return 'This thread is still answering. Wait for it, or start a new question.'
    case 422:
      return 'An attached item could not be found in this matter, or the question is empty. Remove the item and ask again.'
    case 404:
      return 'Chat is not available on this server, or the thread is gone.'
    case 401:
      return 'There is no firm user to ask as.'
    default:
      return `The question could not be sent. ${error.message}`
  }
}
