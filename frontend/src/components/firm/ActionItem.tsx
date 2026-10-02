import type { FactOut } from '@/api/types'
import { SourceChip } from '@/components/shared/SourceChip'
import { DUE_SOON_DAYS, dueDateOf } from '@/lib/facts'
import { daysFromToday, formatDate } from '@/lib/format'
import { WAITING_ON_LABELS } from '@/lib/labels'
import { cn } from '@/lib/utils'

function dueText(days: number): string {
  if (days < -1) return `${-days} days overdue`
  if (days === -1) return '1 day overdue'
  if (days === 0) return 'due today'
  if (days === 1) return 'due tomorrow'
  return `in ${days} days`
}

function details(fact: FactOut): string[] {
  switch (fact.kind) {
    case 'task': {
      const { assignee, waiting_on } = fact.value
      const waiting = waiting_on && waiting_on !== 'firm' ? `Waiting on ${WAITING_ON_LABELS[waiting_on]}` : null
      return [assignee, waiting].filter((part): part is string => Boolean(part))
    }
    case 'record_request':
      return fact.event_date ? [`Requested ${formatDate(fact.event_date)}`] : []
    default:
      return []
  }
}

export function ActionItem({ fact }: { fact: FactOut }) {
  const due = fact.kind === 'record_request' ? null : dueDateOf(fact)
  const days = due === null ? null : daysFromToday(due)
  const tone =
    days === null ? '' : days < 0 ? 'font-medium text-danger' : days <= DUE_SOON_DAYS ? 'text-warning' : ''
  return (
    <li className="flex items-start justify-between gap-3 py-2">
      <div className="min-w-0">
        <p className="text-sm leading-snug">{fact.title}</p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          {due !== null && days !== null && (
            <span className={cn('tabular-nums', tone)}>
              {formatDate(due)}, {dueText(days)}
            </span>
          )}
          {details(fact).map((part, index) => (
            <span key={part}>
              {(index > 0 || due !== null) && ' · '}
              {part}
            </span>
          ))}
        </p>
      </div>
      <SourceChip fact={fact} className="mt-0.5" />
    </li>
  )
}
