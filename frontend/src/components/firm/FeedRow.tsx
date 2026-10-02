import type { FactOut } from '@/api/types'
import { KindBadge } from '@/components/shared/KindBadge'
import { SourceChip } from '@/components/shared/SourceChip'
import { formatDate } from '@/lib/format'

export function FeedRow({ fact }: { fact: FactOut }) {
  return (
    <li className="grid grid-cols-[7rem_7rem_minmax(0,1fr)_auto] items-center gap-3 py-2">
      <span className="text-sm tabular-nums text-muted-foreground">
        {fact.event_date ? formatDate(fact.event_date) : 'Undated'}
      </span>
      <KindBadge kind={fact.kind} />
      <span className="text-sm">{fact.title}</span>
      <SourceChip fact={fact} />
    </li>
  )
}
