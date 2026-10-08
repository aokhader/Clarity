import { useId, useState } from 'react'

import { useMatterInjuries } from '@/api/matters'
import { InjuryRow } from '@/components/firm/InjuryRow'
import { LoadError } from '@/components/shared/LoadError'
import { Loading } from '@/components/shared/Loading'
import { Panel } from '@/components/shared/Panel'
import { Skeleton } from '@/components/ui/skeleton'
import { groupSameInjuries, isInjury } from '@/lib/facts'

/** Injuries shown before the list is expanded; the API returns the most significant first. */
const COLLAPSED_INJURIES = 6

/** Injuries and diagnoses from the records, each listed once and citing every page that states it. */
export function InjuriesList({ matterId }: { matterId: number }) {
  const injuries = useMatterInjuries(matterId)
  const [expanded, setExpanded] = useState(false)
  const listId = useId()
  const groups = groupSameInjuries(injuries.data?.filter(isInjury) ?? [])
  const shown = expanded ? groups : groups.slice(0, COLLAPSED_INJURIES)
  return (
    // Entries, not injuries: the records restate one injury in many wordings (D40).
    <Panel title="Injuries" aside={injuries.isSuccess ? `${groups.length} entries` : undefined}>
      {injuries.isPending && <Loading label="Loading injuries"><Skeleton className="h-16" /></Loading>}
      {injuries.isError && (
        <LoadError what="the injuries" error={injuries.error} onRetry={() => void injuries.refetch()} />
      )}
      {injuries.isSuccess && groups.length === 0 && (
        <p className="text-sm text-muted-foreground">No injuries or diagnoses found in the file.</p>
      )}
      {groups.length > 0 && (
        <ul id={listId} className="flex flex-col gap-3">
          {shown.map((group) => (
            <InjuryRow key={group.key} group={group} />
          ))}
        </ul>
      )}
      {groups.length > COLLAPSED_INJURIES && (
        <button
          type="button"
          aria-expanded={expanded}
          aria-controls={listId}
          onClick={() => setExpanded((open) => !open)}
          className="mt-3 text-sm font-medium text-primary hover:underline"
        >
          {expanded ? 'Show fewer' : `Show all ${groups.length} entries`}
        </button>
      )}
    </Panel>
  )
}
