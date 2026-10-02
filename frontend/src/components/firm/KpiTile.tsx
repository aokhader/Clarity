import { PiggyBank, ShieldCheck, Stethoscope, TrendingDown, TriangleAlert, type LucideIcon } from 'lucide-react'

import type { KpiOut, KpiValueOut } from '@/api/types'
import { RevealOnHover } from '@/components/firm/RevealOnHover'
import { SourceChipList } from '@/components/shared/SourceChipList'
import { formatMoney, formatMoneyRange } from '@/lib/format'
import { cn } from '@/lib/utils'

const KPI_LABELS: Record<KpiOut['name'], string> = {
  case_value: 'Case value',
  coverage: 'Coverage limit',
  medical_specials: 'Medical specials',
  firm_spend: 'Firm spend',
}

/** Each tile keeps one tint so the four figures can be told apart at a glance on a projector. */
const KPI_TONES: Record<KpiOut['name'], { tile: string; label: string; Icon: LucideIcon }> = {
  case_value: { tile: 'border-emerald-100 bg-emerald-50 text-emerald-950', label: 'text-emerald-700', Icon: PiggyBank },
  coverage: { tile: 'border-blue-100 bg-blue-50 text-blue-950', label: 'text-blue-700', Icon: ShieldCheck },
  medical_specials: { tile: 'border-orange-100 bg-orange-50 text-orange-950', label: 'text-orange-700', Icon: Stethoscope },
  firm_spend: { tile: 'border-slate-200 bg-slate-100 text-slate-900', label: 'text-slate-700', Icon: TrendingDown },
}

function amountText(value: KpiValueOut): string {
  if (value.amount_cents !== null) return formatMoney(value.amount_cents)
  return formatMoneyRange(value.low_cents, value.high_cents) ?? 'Amount not stated'
}

/** One KPI: a sourced value, every value when sources disagree, or "Not found in file". */
export function KpiTile({ kpi }: { kpi: KpiOut }) {
  const [only] = kpi.values
  const tone = KPI_TONES[kpi.name]
  return (
    <div className={cn('group/src relative min-w-0 overflow-hidden rounded-xl border px-4 py-4', tone.tile)}>
      <tone.Icon aria-hidden className={cn('absolute -right-1.5 -bottom-3 size-18 opacity-10', tone.label)} />
      <h3 className={cn('text-xs font-semibold uppercase tracking-wider', tone.label)}>{KPI_LABELS[kpi.name]}</h3>
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
          <RevealOnHover>
            <SourceChipList facts={only.facts} />
          </RevealOnHover>
        </div>
      )}
      {kpi.values.length > 1 && (
        <>
          <ul className="mt-1 space-y-0.5">
            {kpi.values.map((value) => (
              <li key={value.facts[0]?.id ?? amountText(value)} className="flex flex-wrap items-center gap-2">
                <span className="whitespace-nowrap text-xl font-semibold tabular-nums">{amountText(value)}</span>
                <RevealOnHover>
                  <SourceChipList facts={value.facts} />
                </RevealOnHover>
              </li>
            ))}
          </ul>
          <p className="mt-1 flex items-center gap-1 text-xs font-medium text-warning">
            <TriangleAlert className="size-3.5" aria-hidden />
            Sources disagree
          </p>
        </>
      )}
      {kpi.basis && <p className={cn('mt-1 text-xs', tone.label)}>{kpi.basis}</p>}
    </div>
  )
}
