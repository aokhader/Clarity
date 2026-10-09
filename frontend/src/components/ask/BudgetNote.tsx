import type { ChatBudgetOut } from '@/api/types'
import { budgetNearlySpent, budgetSpent } from '@/lib/chatErrors'
import { formatDateTime, formatMicroDollars } from '@/lib/format'

/**
 * A line by the Ask button when chat cannot answer yet (no model configured) or when
 * most of the day's budget is gone. A spent budget is said by the composer, which also
 * turns Ask off. The figures are the server's.
 */
export function BudgetNote({ budget }: { budget: ChatBudgetOut | undefined }) {
  if (budget === undefined) return null
  if (!budget.configured) {
    return (
      <p className="text-xs text-muted-foreground">
        Chat isn&apos;t configured. Set <code>CHAT_MODEL</code>, <code>CHAT_PRICE_IN</code> and{' '}
        <code>CHAT_PRICE_OUT</code> in <code>.env</code>.
      </p>
    )
  }
  if (budgetSpent(budget) || !budgetNearlySpent(budget)) return null
  return (
    <p className="text-xs text-warning tabular-nums">
      {formatMicroDollars(budget.spent_today_micro_usd)} of today&apos;s {formatMicroDollars(budget.cap_micro_usd)} chat
      budget spent; it resets {formatDateTime(budget.resets_at)}.
    </p>
  )
}
