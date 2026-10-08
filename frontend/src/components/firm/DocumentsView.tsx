import { useState } from 'react'

import { useMatterTimeline } from '@/api/matters'
import type { FactOut, SourceType } from '@/api/types'
import { LoadError } from '@/components/shared/LoadError'
import { Panel } from '@/components/shared/Panel'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDate } from '@/lib/format'
import { SOURCE_LABELS } from '@/lib/labels'
import { useSourceDrawer } from '@/lib/useSourceDrawer'
import { cn } from '@/lib/utils'

type SourceGroup = { sourceId: number; type: SourceType; facts: FactOut[] }

/** Every source the facts cite, once each, in the order the timeline lists them. */
function groupBySource(facts: FactOut[]): SourceGroup[] {
  const groups = new Map<number, SourceGroup>()
  for (const fact of facts) {
    const group = groups.get(fact.source_id) ?? { sourceId: fact.source_id, type: fact.source_type, facts: [] }
    group.facts.push(fact)
    groups.set(fact.source_id, group)
  }
  return [...groups.values()]
}

function firstDate(facts: FactOut[]): string | null {
  const dates = facts.map((fact) => fact.event_date).filter((date): date is string => date !== null)
  return dates.sort()[0] ?? null
}

/** The documents page: each cited source with what it says, and links that open it. */
export function DocumentsView({ matterId }: { matterId: number }) {
  const timeline = useMatterTimeline(matterId, null, '')
  const drawer = useSourceDrawer()
  const [filter, setFilter] = useState<SourceType | null>(null)

  if (timeline.isPending) return <Skeleton className="h-96 w-full" />
  if (timeline.isError) {
    return <LoadError what="the documents" error={timeline.error} onRetry={() => void timeline.refetch()} />
  }

  const sources = groupBySource(timeline.data)
  const types = [...new Set(sources.map((source) => source.type))]
  const shownTypes = filter === null ? types : [filter]

  return (
    <div className="space-y-6">
      <div role="group" aria-label="Filter by source type" className="flex flex-wrap gap-2">
        {[null, ...types].map((type) => {
          const count = type === null ? sources.length : sources.filter((source) => source.type === type).length
          return (
            <button
              key={type ?? 'all'}
              type="button"
              aria-pressed={filter === type}
              onClick={() => setFilter(type)}
              className={cn(
                'flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm font-medium transition-colors',
                filter === type ? 'border-primary bg-primary text-primary-foreground' : 'border-input bg-card hover:bg-muted',
              )}
            >
              {type === null ? 'All' : SOURCE_LABELS[type]}
              <span className="rounded-sm bg-current/10 px-1.5 text-xs font-semibold">{count}</span>
            </button>
          )
        })}
      </div>
      {sources.length === 0 && <p className="text-sm text-muted-foreground">No sources are cited yet.</p>}
      {shownTypes.map((type) => {
        const ofType = sources.filter((source) => source.type === type)
        return (
          <Panel key={type} title={SOURCE_LABELS[type]} aside={ofType.length}>
            <ul className="divide-y">
              {ofType.map((source) => {
                const date = firstDate(source.facts)
                return (
                  <li key={source.sourceId} className="grid grid-cols-1 gap-x-4 gap-y-1 py-3 sm:grid-cols-[8rem_minmax(0,1fr)]">
                    <span className={cn('text-sm tabular-nums', date ? 'text-foreground/80' : 'text-muted-foreground')}>
                      {date ? formatDate(date) : 'Undated'}
                    </span>
                    <ul className="space-y-1">
                      {source.facts.map((fact) => (
                        <li key={fact.id}>
                          <button
                            type="button"
                            onClick={() => drawer.open(fact.id)}
                            className="text-left text-[15px] text-primary hover:underline"
                          >
                            {fact.title}
                            {fact.page_no !== null && <span className="ml-1.5 text-muted-foreground">p.{fact.page_no}</span>}
                          </button>
                        </li>
                      ))}
                    </ul>
                  </li>
                )
              })}
            </ul>
          </Panel>
        )
      })}
    </div>
  )
}
