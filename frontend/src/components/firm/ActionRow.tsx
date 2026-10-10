import type { FactOut } from '@/api/types'
import { factsRef } from '@/lib/askItems'
import { actionDueDate, actionOwner, dueTone } from '@/lib/facts'
import { daysFromToday, formatDate, formatDueIn } from '@/lib/format'
import { WAITING_ON_LABELS } from '@/lib/labels'
import { useSourceDrawer } from '@/lib/useSourceDrawer'
import { useAskTarget } from '@/lib/useAskTarget'
import { cn } from '@/lib/utils'

/** "Open request", not "Waiting": a record request does not say who it waits on (D40). */
export type ActionStatus = 'Overdue' | 'Open request' | 'Upcoming' | 'Scheduled'

/** Red is kept for what is overdue; the other statuses are told apart by their word. */
const STATUS_STYLES: Record<ActionStatus, string> = {
  Overdue: 'bg-danger-soft text-danger',
  'Open request': 'bg-muted text-foreground',
  Upcoming: 'bg-muted text-foreground',
  Scheduled: 'bg-muted text-muted-foreground',
}

function noteOf(fact: FactOut): string | null {
  if (fact.kind === 'task' && fact.value.waiting_on && fact.value.waiting_on !== 'firm') {
    return `Waiting on ${WAITING_ON_LABELS[fact.value.waiting_on]}`
  }
  if (fact.kind === 'record_request' && fact.event_date) return `Requested ${formatDate(fact.event_date)}`
  return null
}

/** One task, deadline, or record request in the action table. Its title is the button that opens its source. */
export function ActionRow({ fact, status }: { fact: FactOut; status: ActionStatus }) {
  const drawer = useSourceDrawer()
  const due = actionDueDate(fact)
  const days = due === null ? null : daysFromToday(due)
  const note = noteOf(fact)
  const owner = actionOwner(fact)
  const askTarget = useAskTarget(factsRef([fact]), 'deadline')
  return (
    <tr {...askTarget} className="border-b align-top transition-colors hover:bg-muted">
      <td className="px-6 py-3.5">
        <button
          type="button"
          onClick={() => drawer.open(fact.id)}
          className="cursor-pointer text-left text-[15px] text-foreground underline-offset-4 hover:text-primary hover:underline"
        >
          {fact.title}
        </button>
        {(note || fact.confidence === 'low') && (
          <span className="mt-0.5 flex flex-wrap items-center gap-2 text-[13px] text-muted-foreground">
            {note}
            {/* The chip carried the low-confidence marker; the row keeps it. */}
            {fact.confidence === 'low' && (
              <span className="rounded-sm border border-dashed border-warning px-1.5 text-[11px] font-medium text-warning">
                Low confidence
              </span>
            )}
          </span>
        )}
      </td>
      <td className="px-3 py-3.5 tabular-nums">
        <span className="block text-muted-foreground">{due ? formatDate(due) : '—'}</span>
        {days !== null && <span className={cn('block text-[13px] font-medium', dueTone(days))}>{formatDueIn(days)}</span>}
      </td>
      <td className="px-3 py-3.5 text-sm text-muted-foreground">{owner ?? '—'}</td>
      <td className="py-3.5 pr-6 pl-3">
        <span className={cn('inline-block rounded-sm px-2 py-0.5 text-[13px] font-medium', STATUS_STYLES[status])}>
          {status}
        </span>
      </td>
    </tr>
  )
}
