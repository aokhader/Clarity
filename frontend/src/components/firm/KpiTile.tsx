import { PiggyBank, ShieldCheck, Stethoscope, TrendingDown, TriangleAlert, type LucideIcon } from 'lucide-react'

import type { KpiOut } from '@/api/types'
import { KpiLeadFigure } from '@/components/firm/KpiLeadFigure'
import { KpiValueRow } from '@/components/firm/KpiValueRow'
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

/**
 * One KPI. With no values: "Not found in file". When the values are figures for the same
 * thing that disagree, all are listed as equals under a warning. Otherwise the first leads,
 * and the rest are separate entries beneath it, labelled: on the Coverage tile, the
 * server puts the defendant's liability limit first and the client's own policies after (D19).
 */
export function KpiTile({ kpi }: { kpi: KpiOut }) {
  const [lead, ...others] = kpi.values
  const tone = KPI_TONES[kpi.name]
  const leads = lead !== undefined && !kpi.sources_disagree
  return (
    <div className={cn('group/src relative flex min-w-0 flex-col overflow-hidden rounded-xl border px-4 py-4', tone.tile)}>
      <tone.Icon aria-hidden className={cn('absolute -right-1.5 -bottom-3 size-18 opacity-10', tone.label)} />
      <h3 className={cn('text-xs font-semibold uppercase tracking-wider', tone.label)}>{KPI_LABELS[kpi.name]}</h3>
      {lead === undefined && <p className="mt-2 flex h-10 items-center text-lg text-muted-foreground">Not found in file</p>}
      {leads && (
        <>
          {/* The lead's chips sit in the corner, so however many there are, every figure starts on the same line. */}
          <div className="absolute top-3 right-3 whitespace-nowrap">
            <RevealOnHover>
              <SourceChipList facts={lead.facts} max={2} />
            </RevealOnHover>
          </div>
          <KpiLeadFigure value={lead} />
          {lead.label && <p className={cn('text-xs', tone.label)}>{lead.label}</p>}
          {others.length > 0 && (
            <ul aria-label="Also on file" className="mt-3 space-y-1.5 border-t border-foreground/10 pt-2">
              {others.map((value, index) => (
                <KpiValueRow key={value.facts[0]?.id ?? index} value={value} size="small" labelClass={tone.label} />
              ))}
            </ul>
          )}
        </>
      )}
      {lead !== undefined && !leads && (
        <ul className="mt-2 space-y-1">
          {kpi.values.map((value, index) => (
            <KpiValueRow key={value.facts[0]?.id ?? index} value={value} size="large" labelClass={tone.label} />
          ))}
        </ul>
      )}
      <div className="mt-auto space-y-0.5 pt-3">
        {kpi.sources_disagree && (
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
