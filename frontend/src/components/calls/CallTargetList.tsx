import { useCallTargets } from '@/api/calls'
import { ApiError } from '@/api/client'
import type { CallTargetOut } from '@/api/types'
import { CallTargetRow } from '@/components/calls/CallTargetRow'
import { LoadError } from '@/components/shared/LoadError'
import { Loading } from '@/components/shared/Loading'
import { Panel } from '@/components/shared/Panel'
import { Skeleton } from '@/components/ui/skeleton'

type CallTargetListProps = {
  matterId: number
  chosenId: string | null
  /** Null while a call is on, so another cannot be opened over it. */
  onChoose: ((target: CallTargetOut) => void) | null
}

/** Who to call next: the open items waiting on someone, as the server lists them. */
export function CallTargetList({ matterId, chosenId, onChoose }: CallTargetListProps) {
  const targets = useCallTargets(matterId)
  return (
    <Panel title="Who to call next" aside={targets.data?.length}>
      {targets.isPending && <Loading label="Loading who to call"><Skeleton className="h-24 w-full" /></Loading>}
      {targets.isError &&
        (targets.error instanceof ApiError && targets.error.status === 404 ? (
          <p className="text-sm text-muted-foreground">
            Who to call next is listed here once the server side of Calls is in place.
          </p>
        ) : (
          <LoadError what="who to call next" error={targets.error} onRetry={() => void targets.refetch()} />
        ))}
      {targets.isSuccess && targets.data.length === 0 && (
        <p className="text-sm text-muted-foreground">No open item is waiting on someone, so no call is due.</p>
      )}
      {targets.isSuccess && targets.data.length > 0 && (
        <ul className="-my-3 divide-y">
          {targets.data.map((target) => (
            <CallTargetRow
              key={target.target_id}
              target={target}
              chosen={target.target_id === chosenId}
              onChoose={onChoose && (() => onChoose(target))}
            />
          ))}
        </ul>
      )}
    </Panel>
  )
}
