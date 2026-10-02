import type { FactOut } from '@/api/types'
import { RevealOnHover } from '@/components/firm/RevealOnHover'
import { SourceChip } from '@/components/shared/SourceChip'
import { formatDate } from '@/lib/format'
import { KIND_LABELS } from '@/lib/labels'

/** One fact in What Matters and the timeline: date, kind, and what it says. */
export function FeedRow({ fact }: { fact: FactOut }) {
  return (
    <li className="group/src grid grid-cols-[7.5rem_8rem_minmax(0,1fr)] items-center gap-4 py-3">
      <span className={fact.event_date ? 'text-sm tabular-nums text-slate-600' : 'text-sm text-slate-400'}>
        {fact.event_date ? formatDate(fact.event_date) : 'Undated'}
      </span>
      <span className="text-[11.5px] font-semibold tracking-[0.08em] text-muted-foreground uppercase">
        {KIND_LABELS[fact.kind]}
      </span>
      <span className="flex items-center gap-2 text-[15px]">
        <span className="min-w-0">{fact.title}</span>
        <RevealOnHover>
          <SourceChip fact={fact} />
        </RevealOnHover>
      </span>
    </li>
  )
}
