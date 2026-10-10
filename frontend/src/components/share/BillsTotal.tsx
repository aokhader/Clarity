import type { ProviderBillsTotalOut } from '@/api/types'
import { formatMoney } from '@/lib/format'

/**
 * What the office billed, from the server: each charge counted once, even when the
 * firm's ledger, a note, and the itemized bill all record it, and liens left out.
 */
export function BillsTotal({ total }: { total: ProviderBillsTotalOut }) {
  return (
    <div className="rounded-lg bg-muted px-5 py-4">
      <p className="text-xs font-semibold tracking-[0.08em] text-muted-foreground uppercase">Total billed by your office</p>
      <p className="mt-1 text-3xl font-semibold tabular-nums text-foreground">{formatMoney(total.amount_cents)}</p>
      <p className="mt-1 text-[13px] text-muted-foreground">
        Across {total.bill_count} {total.bill_count === 1 ? 'bill' : 'bills'} on file
      </p>
    </div>
  )
}
