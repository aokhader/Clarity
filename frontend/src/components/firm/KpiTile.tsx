import { PiggyBank, ShieldCheck, Stethoscope, TrendingDown, TriangleAlert, type LucideIcon } from 'lucide-react'

import type { KpiOut } from '@/api/types'
import { KpiFigure } from '@/components/firm/KpiFigure'
import { RevealOnHover } from '@/components/firm/RevealOnHover'
import { SourceChipList } from '@/components/shared/SourceChipList'
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

/** One KPI: a sourced value, every value when sources disagree, or "Not found in file". */
export function KpiTile({ kpi }: { kpi: KpiOut }) {
  const [only] = kpi.values
  const tone = KPI_TONES[kpi.name]
  return (
    <div className={cn('group/src relative flex min-w-0 flex-col overflow-hidden rounded-xl border px-4 py-4', tone.tile)}>
      <tone.Icon aria-hidden className={cn('absolute -right-1.5 -bottom-3 size-18 opacity-10', tone.label)} />
      <h3 className={cn('text-xs font-semibold uppercase tracking-wider', tone.label)}>{KPI_LABELS[kpi.name]}</h3>
      {/* A single value's chips sit in the corner, so however many there are, every figure starts on the same line. */}
      {kpi.values.length === 1 && only && (
        <div className="absolute top-3 right-3 whitespace-nowrap">
          <RevealOnHover>
            <SourceChipList facts={only.facts} max={2} />
          </RevealOnHover>
        </div>
      )}
      {kpi.values.length === 0 && <p className="mt-2 flex h-10 items-center text-lg text-muted-foreground">Not found in file</p>}
      {kpi.values.length === 1 && only && (
        <>
          <p
            className={cn(
              'mt-2 flex h-10 items-baseline whitespace-nowrap font-semibold tabular-nums leading-10',
              // A range is twice as long as an amount, so it steps down a size to stay on one line.
              only.amount_cents === null ? 'text-2xl' : 'text-kpi',
            )}
          >
            <KpiFigure value={only} />
          </p>
          {only.label && <p className={cn('text-xs', tone.label)}>{only.label}</p>}
        </>
      )}
      {kpi.values.length > 1 && (
        <ul className="mt-2 space-y-1">
          {kpi.values.map((value, index) => (
            <li key={value.facts[0]?.id ?? index} className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="whitespace-nowrap text-xl font-semibold tabular-nums">
                  <KpiFigure value={value} />
                </p>
                {value.label && <p className={cn('text-xs', tone.label)}>{value.label}</p>}
              </div>
              <RevealOnHover>
                <SourceChipList facts={value.facts} max={1} />
              </RevealOnHover>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-auto space-y-0.5 pt-3">
        {kpi.values.length > 1 && (
          <p className="flex items-center gap-1 text-xs font-medium text-warning">
            <TriangleAlert className="size-3.5" aria-hidden />
            Sources disagree
          </p>
        )}
        {kpi.basis && <p className={cn('text-xs', tone.label)}>{kpi.basis}</p>}
      </div>
    </div>
  )
}
