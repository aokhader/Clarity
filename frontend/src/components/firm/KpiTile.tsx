import { TriangleAlert } from 'lucide-react'

import type { KpiOut, KpiValueOut } from '@/api/types'
import { SourceChipList } from '@/components/shared/SourceChipList'
import { formatMoney, formatMoneyRange } from '@/lib/format'
import { cn } from '@/lib/utils'

const KPI_LABELS: Record<KpiOut['name'], string> = {
  case_value: 'Case value',
  coverage: 'Coverage limit',
  medical_specials: 'Medical specials',
  firm_spend: 'Firm spend',
}

function amountText(value: KpiValueOut): string {
  if (value.amount_cents !== null) return formatMoney(value.amount_cents)
  return formatMoneyRange(value.low_cents, value.high_cents) ?? 'Amount not stated'
}

/** One KPI: a sourced value, every value when sources disagree, or "Not found in file". */
export function KpiTile({ kpi }: { kpi: KpiOut }) {
  const [only] = kpi.values
  return (
    <div className="min-w-0 px-5 py-4">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{KPI_LABELS[kpi.name]}</h3>
      {kpi.values.length === 0 && <p className="mt-2 text-lg text-muted-foreground">Not found in file</p>}
      {kpi.values.length === 1 && only && (
        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1">
          {/* A range is twice as long as an amount, so it steps down a size to stay on one line. */}
          <span
            className={cn(
              'whitespace-nowrap font-semibold tabular-nums',
              only.amount_cents === null ? 'text-2xl' : 'text-kpi',
            )}
          >
            {amountText(only)}
          </span>
          <SourceChipList facts={only.facts} />
        </div>
      )}
      {kpi.values.length > 1 && (
        <>
          <ul className="mt-1 space-y-0.5">
            {kpi.values.map((value) => (
              <li key={value.facts[0]?.id ?? amountText(value)} className="flex flex-wrap items-center gap-2">
                <span className="whitespace-nowrap text-xl font-semibold tabular-nums">{amountText(value)}</span>
                <SourceChipList facts={value.facts} />
              </li>
            ))}
          </ul>
          <p className="mt-1 flex items-center gap-1 text-xs font-medium text-warning">
            <TriangleAlert className="size-3.5" aria-hidden />
            Sources disagree
          </p>
        </>
      )}
      {kpi.basis && <p className="mt-1 text-xs text-muted-foreground">{kpi.basis}</p>}
    </div>
  )
}
