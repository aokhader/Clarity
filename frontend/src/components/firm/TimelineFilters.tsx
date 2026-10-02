import { Search } from 'lucide-react'
import { useId } from 'react'

import type { FactKind } from '@/api/types'
import { KIND_LABELS } from '@/lib/labels'

const KIND_OPTIONS = (Object.entries(KIND_LABELS) as [FactKind, string][]).sort(([, a], [, b]) =>
  a.localeCompare(b),
)

function isFactKind(value: string): value is FactKind {
  return value in KIND_LABELS
}

type TimelineFiltersProps = {
  kind: FactKind | null
  onKindChange: (kind: FactKind | null) => void
  text: string
  onTextChange: (text: string) => void
}

export function TimelineFilters({ kind, onKindChange, text, onTextChange }: TimelineFiltersProps) {
  const kindId = useId()
  const searchId = useId()
  return (
    <div className="mb-3 flex items-center gap-2">
      <label htmlFor={kindId} className="sr-only">
        Kind of fact
      </label>
      <select
        id={kindId}
        value={kind ?? ''}
        onChange={(event) => onKindChange(isFactKind(event.target.value) ? event.target.value : null)}
        className="h-8 rounded-md border bg-card px-2 text-sm focus-visible:outline-2 focus-visible:outline-ring"
      >
        <option value="">All kinds</option>
        {KIND_OPTIONS.map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>
      <div className="relative flex-1">
        <Search className="pointer-events-none absolute top-2 left-2 size-4 text-muted-foreground" aria-hidden />
        <label htmlFor={searchId} className="sr-only">
          Search the timeline
        </label>
        <input
          id={searchId}
          type="search"
          value={text}
          maxLength={200}
          onChange={(event) => onTextChange(event.target.value)}
          placeholder="Search titles and quotes"
          className="h-8 w-full rounded-md border bg-card pr-2 pl-8 text-sm focus-visible:outline-2 focus-visible:outline-ring"
        />
      </div>
    </div>
  )
}
