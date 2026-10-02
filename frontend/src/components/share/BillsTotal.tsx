import type { ProviderBillsTotalOut } from '@/api/types'
import { formatMoney } from '@/lib/format'

/**
 * What the office billed, from the server: each charge counted once, even when the
 * firm's ledger, a note, and the itemized bill all record it, and liens left out.
 */
export function BillsTotal({ total }: { total: ProviderBillsTotalOut }) {
  return (
    <div className="rounded-xl border border-orange-100 bg-orange-50 px-5 py-4">
      <p className="text-xs font-semibold tracking-[0.08em] text-orange-700 uppercase">Total billed by your office</p>
      <p className="mt-1 text-3xl font-extrabold tabular-nums text-orange-950">{formatMoney(total.amount_cents)}</p>
      <p className="mt-1 text-[13px] text-orange-700">
        Across {total.bill_count} {total.bill_count === 1 ? 'bill' : 'bills'} on file
      </p>
    </div>
  )
}
