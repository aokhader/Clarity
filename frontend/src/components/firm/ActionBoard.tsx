import { CalendarDays, CalendarX, Hourglass, Users } from 'lucide-react'
import { useState } from 'react'

import { useMatterActions, useMatterTimeline } from '@/api/matters'
import type { FactOut } from '@/api/types'
import { ActionCountTile } from '@/components/firm/ActionCountTile'
import { ACTION_COLUMNS, ActionRow, type ActionStatus } from '@/components/firm/ActionRow'
import { LoadError } from '@/components/shared/LoadError'
import { Panel } from '@/components/shared/Panel'
import { Skeleton } from '@/components/ui/skeleton'
import { statuteDeadline } from '@/lib/facts'
import { daysFromToday } from '@/lib/format'
import { cn } from '@/lib/utils'

/** Tasks still to do are upcoming; calendar entries and deadlines are scheduled. */
function upcomingStatus(fact: FactOut): ActionStatus {
  return fact.kind === 'task' ? 'Upcoming' : 'Scheduled'
}

/** Rows shown before the table is expanded; a long tail of old record requests would bury the rest. */
const COLLAPSED_ROWS = 8

/** Counts for the three action groups and the statute, over one table of everything open. */
export function ActionBoard({ matterId }: { matterId: number }) {
  const actions = useMatterActions(matterId)
  const [expanded, setExpanded] = useState(false)
  const deadlines = useMatterTimeline(matterId, 'deadline', '')
  const statute = deadlines.data ? statuteDeadline(deadlines.data) : null
  const statuteDays = statute ? daysFromToday(statute.due) : null
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
          <Skeleton className="h-24" />
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
        </div>
      )}
      {actions.isError && (
        <LoadError what="the action board" error={actions.error} onRetry={() => void actions.refetch()} />
      )}
      {actions.isSuccess && (
        <>
          <div className="grid grid-cols-4 gap-4 pt-1">
            <ActionCountTile
              Icon={CalendarX}
              value={String(actions.data.overdue.length)}
              label="Overdue"
              tone="danger"
            />
            <ActionCountTile
              Icon={CalendarDays}
              value={String(actions.data.upcoming.length)}
              label="Upcoming"
              tone="info"
            />
            <ActionCountTile
              Icon={Users}
              value={String(actions.data.waiting_on_others.length)}
              label="Waiting on others"
              tone="warning"
            />
            <ActionCountTile
              Icon={Hourglass}
              value={statuteDays === null ? '—' : statuteDays < 0 ? 'Passed' : String(statuteDays)}
              label="Days to SOL"
              tone="neutral"
            />
          </div>
          <div className="-mx-6 mt-6 -mb-4">
            <div
              className={cn(
                ACTION_COLUMNS,
                'border-y border-slate-100 bg-slate-50 px-6 py-3.5 text-sm font-semibold text-slate-700',
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
                className="w-full px-6 py-3.5 text-left text-sm font-medium text-primary hover:bg-slate-50"
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
