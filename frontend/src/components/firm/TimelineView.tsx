import { useState } from 'react'

import { useMatterTimeline } from '@/api/matters'
import type { FactKind } from '@/api/types'
import { FeedRow } from '@/components/firm/FeedRow'
import { TimelineFilters } from '@/components/firm/TimelineFilters'
import { LoadError } from '@/components/shared/LoadError'
import { Loading } from '@/components/shared/Loading'
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
    body = <Loading label="Loading the timeline"><Skeleton className="h-48" /></Loading>
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
      // Focusable, so the list scrolls from the keyboard too (WCAG 2.1.1).
      <div
        role="region"
        aria-label="Timeline, scrollable"
        tabIndex={0}
        className="max-h-[70vh] space-y-4 overflow-y-auto pr-1"
        aria-busy={timeline.isPlaceholderData}
      >
        {/* Months are plain sections under their headings, not named regions. */}
        {groupByMonth(timeline.data).map((group) => (
          <section key={group.key}>
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

  // Present before results change, so a new count is announced as the filters narrow it.
  const resultCount = timeline.isSuccess
    ? `${timeline.data.length} ${timeline.data.length === 1 ? 'fact' : 'facts'}${filtered ? ' match' : ''}`
    : ''
  return (
    <>
      <TimelineFilters kind={kind} onKindChange={setKind} text={text} onTextChange={setText} />
      <p role="status" className="sr-only">
        {resultCount}
      </p>
      {body}
    </>
  )
}
