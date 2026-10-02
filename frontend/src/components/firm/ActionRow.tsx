import type { FactOut } from '@/api/types'
import { RevealOnHover } from '@/components/firm/RevealOnHover'
import { SourceChip } from '@/components/shared/SourceChip'
import { DUE_SOON_DAYS, dueDateOf } from '@/lib/facts'
import { daysFromToday, formatDate } from '@/lib/format'
import { WAITING_ON_LABELS } from '@/lib/labels'
import { cn } from '@/lib/utils'

export type ActionStatus = 'Overdue' | 'Waiting' | 'Upcoming' | 'Scheduled'

const STATUS_STYLES: Record<ActionStatus, string> = {
  Overdue: 'bg-red-100 text-red-700',
  Waiting: 'bg-orange-100 text-orange-700',
  Upcoming: 'bg-blue-100 text-blue-700',
  Scheduled: 'bg-slate-100 text-slate-700',
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
  if (days <= DUE_SOON_DAYS) return 'text-orange-700'
  return 'text-muted-foreground'
}

function noteOf(fact: FactOut): string | null {
  if (fact.kind === 'task' && fact.value.waiting_on && fact.value.waiting_on !== 'firm') {
    return `Waiting on ${WAITING_ON_LABELS[fact.value.waiting_on]}`
  }
  if (fact.kind === 'record_request' && fact.event_date) return `Requested ${formatDate(fact.event_date)}`
  return null
}

/** One task, deadline, or record request in the action table. */
export function ActionRow({ fact, status }: { fact: FactOut; status: ActionStatus }) {
  // A record request's date is when it was sent, not when it is due.
  const due = fact.kind === 'record_request' ? null : dueDateOf(fact)
  const days = due === null ? null : daysFromToday(due)
  const note = noteOf(fact)
  const owner = fact.kind === 'task' ? fact.value.assignee : null
  return (
    <li className={cn(ACTION_COLUMNS, 'group/src items-center border-b border-slate-100 px-6 py-4 text-[15px]')}>
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="flex items-center gap-2">
          <span className="min-w-0">{fact.title}</span>
          <RevealOnHover>
            <SourceChip fact={fact} />
          </RevealOnHover>
        </span>
        {note && <span className="text-[13px] text-muted-foreground">{note}</span>}
      </div>
      <div className="flex flex-col gap-0.5 tabular-nums">
        <span className="text-slate-600">{due ? formatDate(due) : '—'}</span>
        {days !== null && <span className={cn('text-[13px] font-medium', dueTone(days))}>{dueText(days)}</span>}
      </div>
      <span className="truncate text-sm text-slate-600">{owner ?? '—'}</span>
      <span>
        <span className={cn('inline-block rounded-full px-2.5 py-1 text-[13px] font-medium', STATUS_STYLES[status])}>
          {status}
        </span>
      </span>
    </li>
  )
}
