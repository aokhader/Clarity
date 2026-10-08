import { useState } from 'react'

import { useMatterActions } from '@/api/matters'
import type { FactOut } from '@/api/types'
import { ACTION_COLUMNS, ActionRow, type ActionStatus } from '@/components/firm/ActionRow'
import { LoadError } from '@/components/shared/LoadError'
import { Panel } from '@/components/shared/Panel'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

/** Tasks still to do are upcoming; calendar entries and deadlines are scheduled. */
function upcomingStatus(fact: FactOut): ActionStatus {
  return fact.kind === 'task' ? 'Upcoming' : 'Scheduled'
}

/** Rows shown before the table is expanded; a long tail of old record requests would bury the rest. */
const COLLAPSED_ROWS = 8

/** One table of everything open. The counts and the statute are on the Overview's Now strip. */
export function ActionBoard({ matterId }: { matterId: number }) {
  const actions = useMatterActions(matterId)
  const [expanded, setExpanded] = useState(false)
  // Overdue first, then what others owe the firm, then what is coming up.
  const rows: { fact: FactOut; status: ActionStatus }[] = actions.data
    ? [
        ...actions.data.overdue.map((fact) => ({ fact, status: 'Overdue' as const })),
        ...actions.data.waiting_on_others.map((fact) => ({ fact, status: 'Waiting' as const })),
        ...actions.data.upcoming.map((fact) => ({ fact, status: upcomingStatus(fact) })),
      ]
    : []
  const shown = expanded ? rows : rows.slice(0, COLLAPSED_ROWS)

  return (
    <Panel title="Action board" className="overflow-hidden">
      {actions.isPending && (
        <div className="space-y-3 pb-2" aria-label="Loading the action board">
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
        </div>
      )}
      {actions.isError && (
        <LoadError what="the action board" error={actions.error} onRetry={() => void actions.refetch()} />
      )}
      {actions.isSuccess && (
        <>
          <div className="-mx-6 -my-4">
            <div
              className={cn(
                ACTION_COLUMNS,
                'border-b bg-muted px-6 py-3 text-sm font-semibold text-muted-foreground',
              )}
            >
              <span>Task</span>
              <span>Due date</span>
              <span>Owner</span>
              <span>Status</span>
            </div>
            <ul>
              {shown.map(({ fact, status }) => (
                <ActionRow key={fact.id} fact={fact} status={status} />
              ))}
            </ul>
            {rows.length === 0 && <p className="px-6 py-4 text-sm text-muted-foreground">Nothing open on this matter.</p>}
            {rows.length > COLLAPSED_ROWS && (
              <button
                type="button"
                onClick={() => setExpanded((open) => !open)}
                className="w-full px-6 py-3.5 text-left text-sm font-medium text-primary hover:bg-muted focus-visible:-outline-offset-2"
              >
                {expanded ? 'Show fewer' : `Show all ${rows.length}`}
              </button>
            )}
          </div>
        </>
      )}
    </Panel>
  )
}
