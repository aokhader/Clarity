import { TriangleAlert } from 'lucide-react'

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

/**
 * One KPI. With no values: "Not found in file". When the values are figures for the same
 * thing that disagree, all are listed as equals under a warning. Otherwise the first leads,
 * and the rest are separate entries beneath it, labelled: on the Coverage tile, the
 * server puts the defendant's liability limit first and the client's own policies after (D19).
 *
 * Coverage keeps its lead even when sources disagree: its values are different policies,
 * not rival figures for one, so a conflict among some of them is a note under the
 * defendant's limit rather than a reason to list every limit as an equal (D37).
 */
export function KpiTile({ kpi }: { kpi: KpiOut }) {
  const [lead, ...others] = kpi.values
  const leads = lead !== undefined && (!kpi.sources_disagree || kpi.name === 'coverage')
  // Under a lead figure the warning is a note beneath it; with no lead it closes the tile.
  const disagreement = kpi.sources_disagree && (
    <p className={cn('flex items-center gap-1 text-xs font-medium text-warning', leads && 'mt-1')}>
      <TriangleAlert className="size-3.5 shrink-0" aria-hidden />
      {leads ? 'Sources disagree on some limits' : 'Sources disagree'}
    </p>
  )
  return (
    // One neutral surface for all four tiles; colour marks only the disagreement note.
    <div className="group/src flex min-w-0 flex-col @min-[60rem]:px-5 @min-[60rem]:first:pl-0 @min-[60rem]:last:pr-0">
      {/* The lead's chips share the label's line, so however many there are, every figure starts on the same line. */}
      <div className="flex min-h-5 items-start justify-between gap-2">
        <h3 className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">{KPI_LABELS[kpi.name]}</h3>
        {leads && (
          <span className="shrink-0 whitespace-nowrap">
            <RevealOnHover>
              <SourceChipList facts={lead.facts} max={2} />
            </RevealOnHover>
          </span>
        )}
      </div>
      {lead === undefined && <p className="mt-1 flex h-8 items-center text-base text-muted-foreground">Not found in file</p>}
      {leads && (
        <>
          <KpiLeadFigure value={lead} />
          {lead.label && <p className="text-xs text-muted-foreground">{lead.label}</p>}
          {disagreement}
          {others.length > 0 && (
            <ul aria-label="Also on file" className="mt-3 space-y-1.5 border-t pt-2">
              {others.map((value, index) => (
                <KpiValueRow key={value.facts[0]?.id ?? index} value={value} size="small" />
              ))}
            </ul>
          )}
        </>
      )}
      {lead !== undefined && !leads && (
        <ul className="mt-2 space-y-1">
          {kpi.values.map((value, index) => (
            <KpiValueRow key={value.facts[0]?.id ?? index} value={value} size="large" />
          ))}
        </ul>
      )}
      <div className="mt-auto space-y-0.5 pt-2">
        {!leads && disagreement}
        {kpi.basis && <p className="text-xs text-muted-foreground">{kpi.basis}</p>}
      </div>
    </div>
  )
}
