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

/** What a refused follow-up says once its thread is closed (D52). */
export const THREAD_CLOSED = 'This thread is closed; start a new question.'

/**
 * A refused question or retry, in a sentence that says what to do. The server refuses a
 * follow-up with 409 both while an answer is being written and once the thread is closed,
 * so the caller says which by the thread it holds.
 */
export function askErrorText(error: Error, threadClosed = false): string {
  if (!(error instanceof ApiError)) return `The question could not be sent. ${error.message}`
  switch (error.status) {
    case 429:
      return BUDGET_SPENT
    case 409:
      return threadClosed ? THREAD_CLOSED : 'This thread is still answering. Wait for it, or start a new question.'
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

/** A refused close, in a sentence that says what to do. */
export function closeErrorText(error: Error): string {
  if (!(error instanceof ApiError)) return `The thread could not be closed. ${error.message}`
  switch (error.status) {
    case 409:
      return 'Wait for the answer before closing.'
    case 404:
      return 'This thread is not on this matter, or chat is not available.'
    case 401:
      return 'There is no firm user to close it as.'
    default:
      return `The thread could not be closed. ${error.message}`
  }
}
