import { useId, useState } from 'react'

import { useMatterActions } from '@/api/matters'
import type { FactOut } from '@/api/types'
import { ActionRow, type ActionStatus } from '@/components/firm/ActionRow'
import { LoadError } from '@/components/shared/LoadError'
import { Loading } from '@/components/shared/Loading'
import { Panel } from '@/components/shared/Panel'
import { Skeleton } from '@/components/ui/skeleton'

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
  const rowsId = useId()
  // Overdue first, then what others owe the firm, then what is coming up.
  const rows: { fact: FactOut; status: ActionStatus }[] = actions.data
    ? [
        ...actions.data.overdue.map((fact) => ({ fact, status: 'Overdue' as const })),
        ...actions.data.waiting_on_others.map((fact) => ({ fact, status: 'Open request' as const })),
        ...actions.data.upcoming.map((fact) => ({ fact, status: upcomingStatus(fact) })),
      ]
    : []
  const shown = expanded ? rows : rows.slice(0, COLLAPSED_ROWS)

  return (
    <Panel title="Action board">
      {actions.isPending && (
        <Loading label="Loading the action board" className="space-y-3 pb-2">
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
        </Loading>
      )}
      {actions.isError && (
        <LoadError what="the action board" error={actions.error} onRetry={() => void actions.refetch()} />
      )}
      {actions.isSuccess && (
        // A data table may scroll sideways on a narrow screen rather than reflow (WCAG 1.4.10).
        <div className="-mx-6 -my-4 overflow-x-auto">
          <table className="w-full min-w-[40rem] border-collapse text-left">
            <caption className="sr-only">Open tasks, deadlines and record requests, overdue first</caption>
            <thead>
              <tr className="border-b bg-muted text-sm text-muted-foreground">
                <th scope="col" className="w-[42%] px-6 py-3 font-semibold">
                  Task
                </th>
                <th scope="col" className="w-[22%] px-3 py-3 font-semibold">
                  Due date
                </th>
                <th scope="col" className="w-[16%] px-3 py-3 font-semibold">
                  Owner
                </th>
                <th scope="col" className="py-3 pr-6 pl-3 font-semibold">
                  Status
                </th>
              </tr>
            </thead>
            <tbody id={rowsId}>
              {shown.map(({ fact, status }) => (
                <ActionRow key={fact.id} fact={fact} status={status} />
              ))}
            </tbody>
          </table>
          {rows.length === 0 && <p className="px-6 py-4 text-sm text-muted-foreground">Nothing open on this matter.</p>}
          {rows.length > COLLAPSED_ROWS && (
            <button
              type="button"
              aria-expanded={expanded}
              aria-controls={rowsId}
              onClick={() => setExpanded((open) => !open)}
              className="w-full px-6 py-3.5 text-left text-sm font-medium text-primary hover:bg-muted focus-visible:-outline-offset-2"
            >
              {expanded ? 'Show fewer' : `Show all ${rows.length}`}
            </button>
          )}
        </div>
      )}
    </Panel>
  )
}
