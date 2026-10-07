import type { KpiValueOut } from '@/api/types'
import { formatMoney, formatMoneyRange } from '@/lib/format'

/** The amount, and for a one-ended value what its one end means (KpiValueOut). */
function figureParts(value: KpiValueOut): { qualifier: string | null; amount: string } {
  if (value.amount_cents !== null) return { qualifier: null, amount: formatMoney(value.amount_cents) }
  if (value.low_cents !== null && value.high_cents === null) {
    return { qualifier: 'At least', amount: formatMoney(value.low_cents) }
  }
  if (value.high_cents !== null && value.low_cents === null) {
    return { qualifier: 'Up to', amount: formatMoney(value.high_cents) }
  }
  return { qualifier: null, amount: formatMoneyRange(value.low_cents, value.high_cents) ?? 'Amount not stated' }
}

/** One KPI figure. "At least" and "Up to" are set small, so the amount keeps its size on a narrow tile. */
export function KpiFigure({ value }: { value: KpiValueOut }) {
  const { qualifier, amount } = figureParts(value)
  return (
    <>
      {qualifier && <span className="mr-1.5 text-xs font-medium">{qualifier}</span>}
      {amount}
    </>
  )
}
