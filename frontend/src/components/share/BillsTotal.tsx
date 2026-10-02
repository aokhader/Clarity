import type { ProviderItemOut } from '@/api/types'
import { formatMoney } from '@/lib/format'

/**
 * The sum of the office's own bills, as listed below it. It adds only what the share
 * already releases, so it reveals nothing the list does not.
 */
export function BillsTotal({ bills }: { bills: ProviderItemOut[] }) {
  const amounts = bills.map((bill) => bill.amount_cents).filter((cents): cents is number => cents !== null)
  if (amounts.length === 0) return null
  const total = amounts.reduce((sum, cents) => sum + cents, 0)
  const unpriced = bills.length - amounts.length
  return (
    <div className="rounded-xl border border-orange-100 bg-orange-50 px-5 py-4">
      <p className="text-xs font-semibold tracking-[0.08em] text-orange-700 uppercase">Total billed by your office</p>
      <p className="mt-1 text-3xl font-extrabold tabular-nums text-orange-950">{formatMoney(total)}</p>
      <p className="mt-1 text-[13px] text-orange-700">
        Across {amounts.length} {amounts.length === 1 ? 'bill' : 'bills'} on file
        {unpriced > 0 && `, plus ${unpriced} without an amount`}
      </p>
    </div>
  )
}
