import type { FactOut } from '@/api/types'
import { MarginCited } from '@/components/firm/MarginCited'
import { starterKindOf } from '@/lib/askStarters'
import { formatDate } from '@/lib/format'
import { LANE_LABELS, laneOf, type Lane } from '@/lib/labels'
import { cn } from '@/lib/utils'

/** Each lane's dot differs in shape as well as colour, so neither is the only cue. */
const LANE_MARKS: Record<Lane, string> = {
  case: 'rounded-full bg-lane-case',
  treatment: 'rounded-[2px] bg-lane-treatment',
  negotiation: 'rotate-45 rounded-[1px] bg-lane-negotiation',
}

/**
 * One key event: its number, date, lane and title, with the record that states it and
 * any that restate it cited in the margin. Every cell sits on the first line's baseline,
 * so a title that wraps leaves the number, date and lane at the top of the row.
 */
export function KeyEventRow({ fact, number }: { fact: FactOut; number: number }) {
  const lane = laneOf(fact.kind)
  return (
    <MarginCited
      facts={[fact, ...fact.restated_by]}
      askStarter={starterKindOf(fact.kind)}
      className="flex items-baseline gap-3 text-[15px]"
    >
      <span aria-hidden className="w-6 shrink-0 text-right text-muted-foreground tabular-nums">
        {number}.
      </span>
      <span className="grid min-w-0 flex-1 grid-cols-1 items-baseline gap-x-3 @min-[40rem]:grid-cols-[6.5rem_7.5rem_minmax(0,1fr)]">
        <span className="text-muted-foreground tabular-nums">
          {fact.event_date ? formatDate(fact.event_date) : 'Undated'}
        </span>
        {/* The dot has no text, so its bottom edge is its baseline: it sits on the line like a bullet. */}
        <span className="inline-flex items-baseline gap-2 text-sm text-muted-foreground">
          <span aria-hidden className={cn('size-2 shrink-0', LANE_MARKS[lane])} />
          {LANE_LABELS[lane]}
        </span>
        <span>{fact.title}</span>
      </span>
    </MarginCited>
  )
}
