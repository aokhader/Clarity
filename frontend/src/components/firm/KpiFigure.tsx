import { Fragment } from 'react'

import type { KpiValueOut } from '@/api/types'
import { formatMoney, formatMoneyRangeEnds } from '@/lib/format'

/** The amount, or a range's two ends, and for a one-ended value what its one end means (KpiValueOut). */
function figureParts(value: KpiValueOut): { qualifier: string | null; amounts: string[] } {
  if (value.amount_cents !== null) return { qualifier: null, amounts: [formatMoney(value.amount_cents)] }
  if (value.low_cents !== null && value.high_cents !== null) {
    return { qualifier: null, amounts: formatMoneyRangeEnds(value.low_cents, value.high_cents) }
  }
  if (value.low_cents !== null) return { qualifier: 'At least', amounts: [formatMoney(value.low_cents)] }
  if (value.high_cents !== null) return { qualifier: 'Up to', amounts: [formatMoney(value.high_cents)] }
  return { qualifier: null, amounts: ['Amount not stated'] }
}

/**
 * One KPI figure. "At least" and "Up to" are set small, so the amount keeps its size on a
 * narrow tile. Each amount is unbreakable, so a range too wide for its tile wraps after the
 * dash rather than being cut off.
 */
export function KpiFigure({ value }: { value: KpiValueOut }) {
  const { qualifier, amounts } = figureParts(value)
  return (
    <>
      {qualifier && (
        <>
          <span className="whitespace-nowrap text-xs font-medium">{qualifier}</span>{' '}
        </>
      )}
      {amounts.map((amount, index) => (
        <Fragment key={index}>
          {index > 0 && ' '}
          <span className="whitespace-nowrap">{amount}</span>
        </Fragment>
      ))}
    </>
  )
}
