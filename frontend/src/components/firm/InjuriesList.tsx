import { Activity } from 'lucide-react'
import { useState } from 'react'

import { useMatterInjuries } from '@/api/matters'
import type { FactOf, FactOut } from '@/api/types'
import { InjuryRow } from '@/components/firm/InjuryRow'
import { LoadError } from '@/components/shared/LoadError'
import { Panel } from '@/components/shared/Panel'
import { Skeleton } from '@/components/ui/skeleton'

function isInjury(fact: FactOut): fact is FactOf<'injury' | 'diagnosis'> {
  return fact.kind === 'injury' || fact.kind === 'diagnosis'
}

/** Injuries shown before the list is expanded; the API returns the most significant first. */
const COLLAPSED_INJURIES = 6

/** Injuries and diagnoses from the records, each citing the page it was read from. */
export function InjuriesList({ matterId }: { matterId: number }) {
  const injuries = useMatterInjuries(matterId)
  const [expanded, setExpanded] = useState(false)
  const facts = injuries.data?.filter(isInjury) ?? []
  const shown = expanded ? facts : facts.slice(0, COLLAPSED_INJURIES)
  return (
    <Panel title="Injuries" icon={<Activity />} aside={injuries.isSuccess ? facts.length : undefined}>
      {injuries.isPending && <Skeleton className="h-16" aria-label="Loading injuries" />}
      {injuries.isError && (
        <LoadError what="the injuries" error={injuries.error} onRetry={() => void injuries.refetch()} />
      )}
      {injuries.isSuccess && facts.length === 0 && (
        <p className="text-sm text-muted-foreground">No injuries or diagnoses found in the file.</p>
      )}
      {facts.length > 0 && (
        <ul className="flex flex-col gap-3">
          {shown.map((fact) => (
            <InjuryRow key={fact.id} fact={fact} />
          ))}
        </ul>
      )}
      {facts.length > COLLAPSED_INJURIES && (
        <button
          type="button"
          onClick={() => setExpanded((open) => !open)}
          className="mt-3 text-sm font-medium text-primary hover:underline"
        >
          {expanded ? 'Show fewer' : `Show all ${facts.length}`}
        </button>
      )}
    </Panel>
  )
}
