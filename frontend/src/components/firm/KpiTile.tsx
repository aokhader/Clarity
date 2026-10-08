import { TriangleAlert } from 'lucide-react'
import { useId } from 'react'

import type { KpiOut } from '@/api/types'
import { KpiAlsoOnFile } from '@/components/firm/KpiAlsoOnFile'
import { KpiLeadFigure } from '@/components/firm/KpiLeadFigure'
import { KpiValueRow } from '@/components/firm/KpiValueRow'
import { SourceChipList } from '@/components/shared/SourceChipList'
import { foldIntoLead } from '@/lib/kpis'
import { cn } from '@/lib/utils'

const KPI_LABELS: Record<KpiOut['name'], string> = {
  case_value: 'Case value',
  coverage: 'Coverage limit',
  medical_specials: 'Medical specials',
  firm_spend: 'Firm spend',
}

const ENTRY_NOUNS: Record<KpiOut['name'], { one: string; many: string }> = {
  case_value: { one: 'value', many: 'values' },
  coverage: { one: 'limit', many: 'limits' },
  medical_specials: { one: 'figure', many: 'figures' },
  firm_spend: { one: 'figure', many: 'figures' },
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
 *
 * An entry that only restates the lead is cited by the lead's chips rather than listed
 * again (foldIntoLead), and past the first entry the rest wait behind a disclosure.
 */
export function KpiTile({ kpi }: { kpi: KpiOut }) {
  const [first, ...rest] = kpi.values
  const leads = first !== undefined && (!kpi.sources_disagree || kpi.name === 'coverage')
  const folded = leads ? foldIntoLead(kpi.name, first, rest) : null
  const labelId = useId()
  const figureId = useId()
  // Under a lead figure the warning is a note beneath it; with no lead it closes the tile.
  const disagreement = kpi.sources_disagree && (
    <p className={cn('flex items-center gap-1 text-xs font-medium text-warning', leads && 'mt-1')}>
      <TriangleAlert className="size-3.5 shrink-0" aria-hidden />
      {leads ? 'Sources disagree on some limits' : 'Sources disagree'}
    </p>
  )
  return (
    // One neutral surface for all four tiles; colour marks only the disagreement note.
    <div className="flex min-w-0 flex-col @min-[60rem]:px-5 @min-[60rem]:first:pl-0 @min-[60rem]:last:pr-0">
      {/* The label has its line to itself, so it never wraps to make room for chips. */}
      <h3 id={labelId} className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
        {KPI_LABELS[kpi.name]}
      </h3>
      {first === undefined && <p className="mt-1 flex h-8 items-center text-base text-muted-foreground">Not found in file</p>}
      {folded && (
        <>
          <KpiLeadFigure value={folded.lead} id={figureId} />
          {/* What the figure is and how it was reached, then its sources, on one line under it. */}
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
            {folded.lead.label && <span>{folded.lead.label}</span>}
            {kpi.basis && <span>{kpi.basis}</span>}
            <SourceChipList facts={folded.lead.facts} max={2} describedBy={`${labelId} ${figureId}`} />
          </p>
          {disagreement}
          {folded.others.length > 0 && <KpiAlsoOnFile values={folded.others} noun={ENTRY_NOUNS[kpi.name]} />}
        </>
      )}
      {first !== undefined && !leads && (
        <>
          <ul className="mt-2 space-y-1">
            {kpi.values.map((value, index) => (
              <KpiValueRow key={value.facts[0]?.id ?? index} value={value} size="large" />
            ))}
          </ul>
          <div className="mt-auto space-y-0.5 pt-2">
            {disagreement}
            {kpi.basis && <p className="text-xs text-muted-foreground">{kpi.basis}</p>}
          </div>
        </>
      )}
    </div>
  )
}
