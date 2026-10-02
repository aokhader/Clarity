import { useMatterInjuries } from '@/api/matters'
import type { FactOf, FactOut } from '@/api/types'
import { InjuryRow } from '@/components/firm/InjuryRow'
import { LoadError } from '@/components/shared/LoadError'
import { Panel } from '@/components/shared/Panel'
import { Skeleton } from '@/components/ui/skeleton'

function isInjury(fact: FactOut): fact is FactOf<'injury' | 'diagnosis'> {
  return fact.kind === 'injury' || fact.kind === 'diagnosis'
}

/** Injuries and diagnoses from the records, each citing the page it was read from. */
export function InjuriesList({ matterId }: { matterId: number }) {
  const injuries = useMatterInjuries(matterId)
  const facts = injuries.data?.filter(isInjury) ?? []
  return (
    <Panel title="Injuries" aside={injuries.isSuccess ? facts.length : undefined}>
      {injuries.isPending && <Skeleton className="h-16" aria-label="Loading injuries" />}
      {injuries.isError && (
        <LoadError what="the injuries" error={injuries.error} onRetry={() => void injuries.refetch()} />
      )}
      {injuries.isSuccess && facts.length === 0 && (
        <p className="text-sm text-muted-foreground">No injuries or diagnoses found in the file.</p>
      )}
      {facts.length > 0 && (
        <ul className="-my-2 divide-y">
          {facts.map((fact) => (
            <InjuryRow key={fact.id} fact={fact} />
          ))}
        </ul>
      )}
    </Panel>
  )
}
