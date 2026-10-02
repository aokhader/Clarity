import { TriangleAlert } from 'lucide-react'

import type { AltValue, Confidence, FactOut } from '@/api/types'
import { KindBadge } from '@/components/shared/KindBadge'
import { formatDate, formatMoney } from '@/lib/format'
import { cn } from '@/lib/utils'

const CONFIDENCE_TEXT: Record<Confidence, string> = {
  high: 'High confidence',
  medium: 'Medium confidence',
  low: 'Low confidence',
}

function altText(alt: AltValue): string {
  const value = [
    alt.amount_cents !== null ? formatMoney(alt.amount_cents) : null,
    alt.on ? formatDate(alt.on) : null,
  ].filter(Boolean)
  const where = alt.page_no !== null ? ` (page ${alt.page_no})` : ''
  return `${value.join(', ') || 'A different value'}${where}`
}

/** The fact itself: kind, date, how sure the file is, and any value that disagrees. */
export function FactSummary({ fact }: { fact: FactOut }) {
  const alternatives = fact.value.alt_values
  return (
    <div className="space-y-1.5 text-sm">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <KindBadge kind={fact.kind} />
        {fact.event_date && <span className="tabular-nums">{formatDate(fact.event_date)}</span>}
        <span
          className={cn(
            'text-xs',
            fact.confidence === 'high' && 'text-success',
            fact.confidence === 'medium' && 'text-muted-foreground',
            fact.confidence === 'low' && 'font-medium text-warning',
          )}
        >
          {CONFIDENCE_TEXT[fact.confidence]}
          {fact.verified && ', verified'}
        </span>
        <span className="text-xs text-muted-foreground">
          {fact.origin === 'code' ? 'Read from a Clio field' : 'Extracted by the model'}
        </span>
      </div>
      {alternatives.length > 0 && (
        <p className="flex items-start gap-1.5 text-xs font-medium text-warning">
          <TriangleAlert className="mt-px size-3.5 shrink-0" aria-hidden />
          The file disagrees. Another reading gives {alternatives.map(altText).join('; ')}.
        </p>
      )}
    </div>
  )
}
