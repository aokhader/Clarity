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
const LOADING = <span aria-label="Loading" className="inline-block h-5 w-36 animate-pulse rounded-md bg-muted align-middle" />

/** A cell's value from its request: loading, failed, the value, or what an empty file says. */
function cellValue(query: { isPending: boolean; isError: boolean }, value: ReactNode, empty: ReactNode): ReactNode {
  if (query.isPending) return LOADING
  if (query.isError) return UNAVAILABLE
  return value ?? empty
}

/** The next step's title, then when it falls due and who owns it. */
function nextStepText({ fact, overdue }: { fact: FactOut; overdue: boolean }): ReactNode {
  const due = actionDueDate(fact)
  const days = due === null ? null : daysFromToday(due)
  const owner = actionOwner(fact)
  const when =
    days !== null ? (
      <span className={cn('font-medium', dueTone(days))}>{formatDueIn(days)}</span>
    ) : overdue ? (
      <span className="font-medium text-danger">Overdue</span>
    ) : null
  return (
    <>
      <p className="font-medium">{fact.title}</p>
      {(when || owner) && (
        <p className="mt-0.5 text-[13px] text-muted-foreground">
          {when}
          {when && owner && ' · '}
          {owner}
        </p>
      )}
    </>
  )
}

/** The statute's date and its countdown: amber within STATUTE_SOON_DAYS, red once passed. */
function statuteText(due: IsoDate): ReactNode {
  const days = daysFromToday(due)
  const tone = days < 0 ? 'text-danger' : days <= STATUTE_SOON_DAYS ? 'text-warning' : 'text-muted-foreground'
  return (
    <>
      <p className="font-medium tabular-nums">{formatDate(due)}</p>
      <p className={cn('mt-0.5 text-[13px] font-medium', tone)}>{formatDaysUntil(days)}</p>
    </>
  )
}

/** How long since the client was last in touch, in words and amber once it is stale. */
function contactText(on: IsoDate): ReactNode {
  const days = -daysFromToday(on)
  return (
    <>
      {days > STALE_CONTACT_DAYS ? (
        <p className="font-medium text-warning">No contact in {days} days</p>
      ) : (
        <p className="font-medium">{formatDaysAgo(on)}</p>
      )}
      <p className="mt-0.5 text-[13px] text-muted-foreground tabular-nums">{formatDate(on)}</p>
    </>
  )
}

/** The open actions counted by group, linking to the action board. */
function toDoText(actions: ActionsOut): ReactNode {
  return (
    <Link to={{ search: '?view=attorney' }} className="text-primary underline-offset-4 hover:underline">
      {actions.overdue.length} overdue · {actions.upcoming.length} upcoming · {actions.waiting_on_others.length}{' '}
      waiting on others
    </Link>
  )
}

/**
 * Where the case is today, in one row: the next step, the statute, the last client
 * contact, and what is open. Each value cites its fact; the counts link to the action
 * board on For Attorney.
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
        <div className="grid grid-cols-1 gap-x-8 gap-y-5 @min-[36rem]:grid-cols-2 @min-[60rem]:grid-cols-4 @min-[60rem]:divide-x">
          <NowCell label="Next step" facts={next ? [next.fact] : []}>
            {cellValue(actions, next && nextStepText(next), <span className="text-muted-foreground">Nothing scheduled</span>)}
          </NowCell>
          <NowCell label="Statute" facts={statute ? [statute.fact] : []}>
            {cellValue(deadlines, statute && statuteText(statute.due), NOT_FOUND)}
          </NowCell>
          <NowCell label="Last client contact" facts={contact ? [contact.fact] : []}>
            {contact ? contactText(contact.on) : <span className="text-muted-foreground">None found in file</span>}
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
