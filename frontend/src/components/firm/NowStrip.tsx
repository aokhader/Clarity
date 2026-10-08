import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { useMatterActions, useMatterTimeline } from '@/api/matters'
import type { ActionsOut, FactOut, IsoDate, MatterHeaderOut } from '@/api/types'
import { NowCell } from '@/components/firm/NowCell'
import { LoadError } from '@/components/shared/LoadError'
import { Section } from '@/components/shared/Section'
import {
  STALE_CONTACT_DAYS,
  STATUTE_SOON_DAYS,
  actionDueDate,
  actionOwner,
  dueTone,
  nextStep,
  statuteDeadline,
} from '@/lib/facts'
import { daysFromToday, formatDate, formatDaysAgo, formatDaysUntil, formatDueIn } from '@/lib/format'
import { cn } from '@/lib/utils'

const NOT_FOUND = <span className="text-muted-foreground">Not found in file</span>
// A failed request is not an empty file, so it never reads "Not found".
const UNAVAILABLE = <span className="text-muted-foreground">Could not load</span>
const LOADING = (
  <span role="status">
    <span className="sr-only">Loading</span>
    <span aria-hidden className="inline-block h-5 w-36 animate-pulse rounded-md bg-muted align-middle" />
  </span>
)

/** A cell's value from its request: loading, failed, the value, or what an empty file says. */
function cellValue(query: { isPending: boolean; isError: boolean }, value: ReactNode, empty: ReactNode): ReactNode {
  if (query.isPending) return LOADING
  if (query.isError) return UNAVAILABLE
  return value ?? empty
}

/** When the next step falls due and who owns it. */
function nextStepDetail({ fact, overdue }: { fact: FactOut; overdue: boolean }): ReactNode {
  const due = actionDueDate(fact)
  const days = due === null ? null : daysFromToday(due)
  const owner = actionOwner(fact)
  const when =
    days !== null ? (
      <span className={cn('font-medium', dueTone(days))}>{formatDueIn(days)}</span>
    ) : overdue ? (
      <span className="font-medium text-danger">Overdue</span>
    ) : null
  if (!when && !owner) return null
  return (
    <span>
      {when}
      {when && owner && ' · '}
      {owner}
    </span>
  )
}

/** The statute's countdown in words: amber within STATUTE_SOON_DAYS, red once passed. */
function statuteDetail(due: IsoDate): ReactNode {
  const days = daysFromToday(due)
  const tone = days < 0 ? 'text-danger' : days <= STATUTE_SOON_DAYS ? 'text-warning' : 'text-muted-foreground'
  return <span className={cn('font-medium', tone)}>{formatDaysUntil(days)}</span>
}

/** How long since the client was last in touch, in words and amber once it is stale. */
function contactValue(on: IsoDate): ReactNode {
  const days = -daysFromToday(on)
  if (days > STALE_CONTACT_DAYS) return <span className="font-medium text-warning">No contact in {days} days</span>
  return <span className="font-medium">{formatDaysAgo(on)}</span>
}

/** The open actions counted by group, linking to the action board. */
function toDoText(actions: ActionsOut): ReactNode {
  return (
    <Link to={{ search: '?view=attorney' }} className="text-primary underline-offset-4 hover:underline">
      {/* "Open requests", not "waiting on others": a record request carries no direction (D40). */}
      {actions.overdue.length} overdue · {actions.upcoming.length} upcoming · {actions.waiting_on_others.length} open
      requests
    </Link>
  )
}

/**
 * Where the case is today, in one row: the next step, the statute, the last client
 * contact, and what is open. Each value cites its fact; the counts link to the action
 * board on For Attorney. The next step gets twice the width, since its title is a
 * sentence where the others are a date or a count.
 */
export function NowStrip({ matterId, header }: { matterId: number; header: MatterHeaderOut }) {
  const actions = useMatterActions(matterId)
  const deadlines = useMatterTimeline(matterId, 'deadline', '')
  const next = actions.data ? nextStep(actions.data) : null
  const statute = deadlines.data ? statuteDeadline(deadlines.data) : null
  const contact = header.last_client_contact
  const failed = [actions, deadlines].filter((query) => query.isError)

  return (
    <Section title="Now">
      <div className="@container">
        <div className="grid grid-cols-1 gap-x-8 gap-y-5 @min-[36rem]:grid-cols-2 @min-[60rem]:grid-cols-[minmax(0,2fr)_repeat(3,minmax(0,1fr))] @min-[60rem]:divide-x">
          <NowCell
            label={next?.overdue ? 'Overdue' : 'Next step'}
            facts={next ? [next.fact] : []}
            detail={next && nextStepDetail(next)}
          >
            {cellValue(
              actions,
              next && <span className="font-medium">{next.fact.title}</span>,
              <span className="text-muted-foreground">Nothing scheduled</span>,
            )}
          </NowCell>
          <NowCell label="Statute" facts={statute ? [statute.fact] : []} detail={statute && statuteDetail(statute.due)}>
            {cellValue(
              deadlines,
              statute && <span className="font-medium tabular-nums">{formatDate(statute.due)}</span>,
              NOT_FOUND,
            )}
          </NowCell>
          <NowCell
            label="Last client contact"
            facts={contact ? [contact.fact] : []}
            detail={contact && <span className="tabular-nums">{formatDate(contact.on)}</span>}
          >
            {contact ? contactValue(contact.on) : <span className="text-muted-foreground">None found in file</span>}
          </NowCell>
          <NowCell label="To do">{cellValue(actions, actions.data && toDoText(actions.data), null)}</NowCell>
        </div>
      </div>
      {failed[0] && (
        <div className="mt-4">
          <LoadError
            what="part of the Now strip"
            error={failed[0].error}
            onRetry={() => failed.forEach((query) => void query.refetch())}
          />
        </div>
      )}
    </Section>
  )
}
