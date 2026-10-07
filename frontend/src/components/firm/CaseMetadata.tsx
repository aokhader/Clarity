import { Activity, Calendar, CircleAlert, FileText, Hourglass, MessageSquare, ShieldCheck, Signpost } from 'lucide-react'
import type { ReactNode } from 'react'

import { useMatterActions, useMatterInjuries, useMatterTimeline } from '@/api/matters'
import type { FactOut, MatterHeaderOut } from '@/api/types'
import { MetadataItem } from '@/components/firm/MetadataItem'
import { LoadError } from '@/components/shared/LoadError'
import { Panel } from '@/components/shared/Panel'
import { STALE_CONTACT_DAYS, dueDateOf, statuteDeadline } from '@/lib/facts'
import { daysFromToday, formatDate, formatDaysAgo, formatElapsed } from '@/lib/format'
import { STAGE_LABELS } from '@/lib/labels'

const NOT_FOUND = <span className="text-muted-foreground">Not found in file</span>
// A failed request is not an empty file, so it never reads "Not found".
const UNAVAILABLE = <span className="text-muted-foreground">Could not load</span>
// A span, not the Skeleton div: the value sits inside the card's button.
const LOADING = <span aria-label="Loading" className="inline-block h-5 w-40 animate-pulse rounded-md bg-muted align-middle" />

/** A card's value from its request: loading, failed, the value, or not found in the file. */
function cardValue(query: { isPending: boolean; isError: boolean }, value: ReactNode): ReactNode {
  if (query.isPending) return LOADING
  if (query.isError) return UNAVAILABLE
  return value ?? NOT_FOUND
}

function mostSignificant(facts: FactOut[] | undefined): FactOut | null {
  if (!facts || facts.length === 0) return null
  return facts.reduce((best, fact) => (fact.significance > best.significance ? fact : best))
}

function inDays(days: number): string {
  if (days === 0) return 'today'
  if (days > 0) return `in ${days} day${days === 1 ? '' : 's'}`
  return `passed ${-days} day${days === -1 ? '' : 's'} ago`
}

/** The case at a glance: each value is a fact from the file, with its source on hover. */
export function CaseMetadata({ matterId, header }: { matterId: number; header: MatterHeaderOut }) {
  const liability = useMatterTimeline(matterId, 'liability', '')
  const deadlines = useMatterTimeline(matterId, 'deadline', '')
  const injuries = useMatterInjuries(matterId)
  const actions = useMatterActions(matterId)

  const { stage, incident, last_client_contact: contact } = header
  const topLiability = mostSignificant(liability.data)
  const topInjury = injuries.data?.find((fact) => fact.kind === 'injury' || fact.kind === 'diagnosis') ?? null
  const statute = deadlines.data ? statuteDeadline(deadlines.data) : null
  const overdue = actions.data?.overdue[0] ?? null
  const overdueDue = overdue ? dueDateOf(overdue) : null
  const staleContact = contact !== null && -daysFromToday(contact.on) > STALE_CONTACT_DAYS
  const failed = [liability, deadlines, injuries, actions].filter((query) => query.isError)

  return (
    <Panel title="Case metadata" icon={<FileText />}>
      {/* Equal rows and equal columns, so every card has the same size. */}
      <div className="grid auto-rows-fr grid-cols-3 gap-4">
        <MetadataItem icon={<Signpost />} label="Case stage" facts={stage.facts}>
          {stage.stage ? (
            <span>
              {STAGE_LABELS[stage.stage]}
              {stage.inferred && <span className="ml-1.5 text-sm text-warning">inferred</span>}
            </span>
          ) : (
            NOT_FOUND
          )}
        </MetadataItem>
        <MetadataItem icon={<Calendar />} label="Date of incident" facts={incident ? [incident.fact] : []}>
          {incident ? (
            <span className="tabular-nums">
              {formatDate(incident.on)} <span className="text-muted-foreground">({formatElapsed(incident.on)} ago)</span>
            </span>
          ) : (
            NOT_FOUND
          )}
        </MetadataItem>
        <MetadataItem icon={<MessageSquare />} label="Last client contact" facts={contact ? [contact.fact] : []}>
          {contact ? (
            <span className={staleContact ? 'font-medium text-warning' : undefined}>{formatDaysAgo(contact.on)}</span>
          ) : (
            <span className="text-muted-foreground">None found in file</span>
          )}
        </MetadataItem>
        <MetadataItem
          icon={<ShieldCheck />}
          label="Liability"
          facts={topLiability ? [topLiability] : []}
          fullText={topLiability?.title}
        >
          {cardValue(liability, topLiability && <span>{topLiability.title}</span>)}
        </MetadataItem>
        <MetadataItem
          icon={<Activity />}
          label="Primary injury"
          facts={topInjury ? [topInjury] : []}
          fullText={topInjury?.title}
        >
          {cardValue(injuries, topInjury && <span>{topInjury.title}</span>)}
        </MetadataItem>
        <MetadataItem icon={<Hourglass />} label="Statute of limitations" facts={statute ? [statute.fact] : []}>
          {cardValue(
            deadlines,
            statute && (
              <span className="tabular-nums">
                {formatDate(statute.due)}{' '}
                <span className="text-muted-foreground">({inDays(daysFromToday(statute.due))})</span>
              </span>
            ),
          )}
        </MetadataItem>
      </div>
      {overdue && (
        <div className="mt-4">
          <MetadataItem icon={<CircleAlert />} label="Overdue" facts={[overdue]} fullText={overdue.title} urgent>
            <span className="tabular-nums">
              {overdueDue ? `${formatDate(overdueDue)} · ` : ''}
              {overdue.title}
              {overdueDue ? ` · ${-daysFromToday(overdueDue)} days overdue` : ''}
            </span>
            {actions.data && actions.data.overdue.length > 1 && (
              <span className="text-sm text-muted-foreground"> · and {actions.data.overdue.length - 1} more</span>
            )}
          </MetadataItem>
        </div>
      )}
      {failed[0] && (
        <div className="mt-4">
          <LoadError
            what="part of the case metadata"
            error={failed[0].error}
            onRetry={() => failed.forEach((query) => void query.refetch())}
          />
        </div>
      )}
    </Panel>
  )
}
