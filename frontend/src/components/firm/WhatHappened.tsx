import { Link } from 'react-router'

import { useMatterInjuries, useMatterTimeline } from '@/api/matters'
import type { IncidentAccountOut } from '@/api/types'
import { MarginCited } from '@/components/firm/MarginCited'
import { LoadError } from '@/components/shared/LoadError'
import { Section } from '@/components/shared/Section'
import { Skeleton } from '@/components/ui/skeleton'
import { groupSameInjuries, isInjury, mostSignificant } from '@/lib/facts'
import { KIND_LABELS } from '@/lib/labels'

/** Injuries on the Overview; the rest are listed on For Attorney. */
const INJURIES_SHOWN = 3

const SUBHEADING = 'mt-5 text-xs font-semibold tracking-[0.08em] text-muted-foreground uppercase'
const NOT_FOUND = <p className="py-1.5 text-[15px] text-muted-foreground">Not found in file</p>

/**
 * What the case is about: the incident as a record the model read describes it (never
 * the date field, D39), then the leading injuries and the leading liability fact. Each
 * line cites its sources in the margin.
 */
export function WhatHappened({ matterId, account }: { matterId: number; account: IncidentAccountOut | null }) {
  const injuries = useMatterInjuries(matterId)
  const liability = useMatterTimeline(matterId, 'liability', '')
  // The server lists injuries treating providers first; grouping keeps that order.
  const groups = groupSameInjuries(injuries.data?.filter(isInjury) ?? [])
  const leadingLiability = mostSignificant(liability.data)

  return (
    <Section title="What happened">
      <div className="@container">
        {account ? (
          <MarginCited as="div" facts={[account.fact]} className="font-serif text-brief text-pretty">
            {account.text}
          </MarginCited>
        ) : (
          NOT_FOUND
        )}

        <h3 className={SUBHEADING}>Injuries</h3>
        {injuries.isPending && <Skeleton className="mt-2 h-12" aria-label="Loading injuries" />}
        {injuries.isError && (
          <div className="mt-2">
            <LoadError what="the injuries" error={injuries.error} onRetry={() => void injuries.refetch()} />
          </div>
        )}
        {injuries.isSuccess &&
          (groups.length === 0 ? (
            NOT_FOUND
          ) : (
            <ul className="mt-1">
              {groups.slice(0, INJURIES_SHOWN).map(({ key, lead, facts }) => (
                <MarginCited key={key} facts={facts} className="text-[15px]">
                  <span className="font-medium">{lead.title}</span>
                  <span className="text-muted-foreground">
                    {' · '}
                    {[KIND_LABELS[lead.kind], lead.value.body_part, lead.value.severity].filter(Boolean).join(' · ')}
                  </span>
                </MarginCited>
              ))}
            </ul>
          ))}
        {groups.length > INJURIES_SHOWN && (
          <Link
            to={{ search: '?view=attorney' }}
            className="mt-1 inline-block text-sm text-primary underline-offset-4 hover:underline"
          >
            All {groups.length} injuries on For Attorney
          </Link>
        )}

        <h3 className={SUBHEADING}>Liability</h3>
        {liability.isPending && <Skeleton className="mt-2 h-6" aria-label="Loading liability" />}
        {liability.isError && (
          <div className="mt-2">
            <LoadError what="the liability facts" error={liability.error} onRetry={() => void liability.refetch()} />
          </div>
        )}
        {liability.isSuccess &&
          (leadingLiability ? (
            <div className="mt-1">
              <MarginCited as="div" facts={[leadingLiability]} className="text-[15px]">
                {leadingLiability.title}
              </MarginCited>
            </div>
          ) : (
            NOT_FOUND
          ))}
      </div>
    </Section>
  )
}
