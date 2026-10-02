import { CalendarDays } from 'lucide-react'

import { useMatterActions } from '@/api/matters'
import { ActionGroup } from '@/components/firm/ActionGroup'
import { LoadError } from '@/components/shared/LoadError'
import { Panel } from '@/components/shared/Panel'
import { Skeleton } from '@/components/ui/skeleton'

export function ActionBoard({ matterId }: { matterId: number }) {
  const actions = useMatterActions(matterId)
  return (
    <Panel title="Action board" icon={<CalendarDays />}>
      {actions.isPending && (
        <div className="space-y-3" aria-label="Loading the action board">
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
        </div>
      )}
      {actions.isError && (
        <LoadError what="the action board" error={actions.error} onRetry={() => void actions.refetch()} />
      )}
      {actions.isSuccess && (
        <div className="space-y-4">
          <ActionGroup title="Overdue" facts={actions.data.overdue} empty="Nothing overdue." urgent />
          <ActionGroup title="Upcoming" facts={actions.data.upcoming} empty="Nothing scheduled." />
          <ActionGroup
            title="Waiting on others"
            facts={actions.data.waiting_on_others}
            empty="Not waiting on anyone."
          />
        </div>
      )}
    </Panel>
  )
}
