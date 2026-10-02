import { useState } from 'react'

import { useMatterTimeline } from '@/api/matters'
import type { FactKind } from '@/api/types'
import { FeedRow } from '@/components/firm/FeedRow'
import { TimelineFilters } from '@/components/firm/TimelineFilters'
import { LoadError } from '@/components/shared/LoadError'
import { Skeleton } from '@/components/ui/skeleton'
import { groupByMonth } from '@/lib/facts'
import { useDebouncedValue } from '@/lib/useDebouncedValue'

const SEARCH_DELAY_MS = 250

/** Every fact by date, grouped by month, with kind and text filters. */
export function TimelineView({ matterId }: { matterId: number }) {
  const [kind, setKind] = useState<FactKind | null>(null)
  const [text, setText] = useState('')
  const query = useDebouncedValue(text.trim(), SEARCH_DELAY_MS)
  const timeline = useMatterTimeline(matterId, kind, query)
  const filtered = kind !== null || query !== ''

  let body
  if (timeline.isPending) {
    body = <Skeleton className="h-48" aria-label="Loading the timeline" />
  } else if (timeline.isError) {
    body = <LoadError what="the timeline" error={timeline.error} onRetry={() => void timeline.refetch()} />
  } else if (timeline.data.length === 0) {
    body = (
      <p className="text-sm text-muted-foreground">
        {filtered ? 'No facts match these filters.' : 'No facts have been extracted for this matter yet.'}
      </p>
    )
  } else {
    body = (
      <div className="max-h-[70vh] space-y-4 overflow-y-auto pr-1" aria-busy={timeline.isPlaceholderData}>
        {groupByMonth(timeline.data).map((group) => (
          <section key={group.key} aria-label={group.label}>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {group.label}
              <span className="ml-2 font-normal normal-case tracking-normal">{group.facts.length}</span>
            </h3>
            <ol className="divide-y">
              {group.facts.map((fact) => (
                <FeedRow key={fact.id} fact={fact} />
              ))}
            </ol>
          </section>
        ))}
      </div>
    )
  }

  return (
    <>
      <TimelineFilters kind={kind} onKindChange={setKind} text={text} onTextChange={setText} />
      {body}
    </>
  )
}
