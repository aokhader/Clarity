import type { FactOut } from '@/api/types'
import { DUE_SOON_DAYS, dueDateOf } from '@/lib/facts'
import { daysFromToday, formatDate } from '@/lib/format'
import { WAITING_ON_LABELS } from '@/lib/labels'
import { useSourceDrawer } from '@/lib/useSourceDrawer'
import { cn } from '@/lib/utils'

export type ActionStatus = 'Overdue' | 'Waiting' | 'Upcoming' | 'Scheduled'

/** Red is kept for what is overdue; the other statuses are told apart by their word. */
const STATUS_STYLES: Record<ActionStatus, string> = {
  Overdue: 'bg-danger-soft text-danger',
  Waiting: 'bg-muted text-foreground',
  Upcoming: 'bg-muted text-foreground',
  Scheduled: 'bg-muted text-muted-foreground',
}

/** Columns shared by the table's heading and its rows. */
export const ACTION_COLUMNS =
  'grid grid-cols-[minmax(0,1.8fr)_minmax(0,1.1fr)_minmax(0,0.7fr)_minmax(0,0.9fr)] gap-4'

function dueText(days: number): string {
  if (days < -1) return `${-days} days overdue`
  if (days === -1) return '1 day overdue'
  if (days === 0) return 'due today'
  if (days === 1) return 'tomorrow'
  return `in ${days} days`
}

function dueTone(days: number): string {
  if (days < 0) return 'text-danger'
  if (days <= DUE_SOON_DAYS) return 'text-warning'
  return 'text-muted-foreground'
}

function noteOf(fact: FactOut): string | null {
  if (fact.kind === 'task' && fact.value.waiting_on && fact.value.waiting_on !== 'firm') {
    return `Waiting on ${WAITING_ON_LABELS[fact.value.waiting_on]}`
  }
  if (fact.kind === 'record_request' && fact.event_date) return `Requested ${formatDate(fact.event_date)}`
  return null
}

/** One task, deadline, or record request in the action table. The whole row opens its source. */
export function ActionRow({ fact, status }: { fact: FactOut; status: ActionStatus }) {
  const drawer = useSourceDrawer()
  // A record request's date is when it was sent, not when it is due.
  const due = fact.kind === 'record_request' ? null : dueDateOf(fact)
  const days = due === null ? null : daysFromToday(due)
  const note = noteOf(fact)
  const owner = fact.kind === 'task' ? fact.value.assignee : null
  return (
    <li className="border-b">
      <button
        type="button"
        onClick={() => drawer.open(fact.id)}
        className={cn(
          ACTION_COLUMNS,
          'w-full cursor-pointer items-center px-6 py-4 text-left text-[15px] transition-colors hover:bg-muted focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring',
        )}
      >
        <span className="flex min-w-0 flex-col gap-0.5">
          <span>{fact.title}</span>
          {(note || fact.confidence === 'low') && (
            <span className="flex flex-wrap items-center gap-2 text-[13px] text-muted-foreground">
              {note}
              {/* The chip carried the low-confidence marker; the row keeps it. */}
              {fact.confidence === 'low' && (
                <span className="rounded-sm border border-dashed border-warning px-1.5 text-[11px] font-medium text-warning">
                  Low confidence
                </span>
              )}
            </span>
          )}
        </span>
        <span className="flex flex-col gap-0.5 tabular-nums">
          <span className="text-muted-foreground">{due ? formatDate(due) : '—'}</span>
          {days !== null && <span className={cn('text-[13px] font-medium', dueTone(days))}>{dueText(days)}</span>}
        </span>
        <span className="truncate text-sm text-muted-foreground">{owner ?? '—'}</span>
        <span>
          <span className={cn('inline-block rounded-sm px-2 py-0.5 text-[13px] font-medium', STATUS_STYLES[status])}>
            {status}
          </span>
        </span>
      </button>
    </li>
  )
}
