import { Link } from 'react-router'

import { useMatterInjuries, useMatterTimeline } from '@/api/matters'
import type { IncidentAccountOut } from '@/api/types'
import { MarginCited } from '@/components/firm/MarginCited'
import { LoadError } from '@/components/shared/LoadError'
import { Loading } from '@/components/shared/Loading'
import { Section } from '@/components/shared/Section'
import { Skeleton } from '@/components/ui/skeleton'
import { groupSameInjuries, isInjury, mostSignificant } from '@/lib/facts'
import { KIND_LABELS } from '@/lib/labels'

/** Injuries on the Overview; the rest are listed on For Attorney. */
const INJURIES_SHOWN = 3

/** One term and its value: a fixed label column, then the value with its chips in the margin. */
const ROW = 'grid grid-cols-1 items-baseline gap-x-4 @min-[40rem]:grid-cols-[7rem_minmax(0,1fr)]'
const TERM = 'text-xs font-semibold tracking-[0.08em] text-muted-foreground uppercase'
const NOT_FOUND = <p className="py-1.5 text-[15px] text-muted-foreground">Not found in file</p>

/**
 * What the case is about, as a definition list: the incident as the records describe it
 * (never the date field, D39), the leading injuries, and the leading liability fact. Each
 * value cites its sources in the margin.
 */
export function WhatHappened({ matterId, account }: { matterId: number; account: IncidentAccountOut | null }) {
  const injuries = useMatterInjuries(matterId)
  const liability = useMatterTimeline(matterId, 'liability', '')
  // The server lists injuries treating providers first; grouping keeps that order.
  const groups = groupSameInjuries(injuries.data?.filter(isInjury) ?? [])
  const shownInjuries = groups.slice(0, INJURIES_SHOWN)
  const leadingLiability = mostSignificant(liability.data)

  return (
    <Section title="What happened">
      <dl className="@container">
        <div className={ROW}>
          <dt className={TERM}>Incident</dt>
          <dd className="min-w-0">
            {account ? (
              // The record the account comes from, then every other record that gives the same account.
              <MarginCited
                as="div"
                facts={[account.fact, ...account.restated_by]}
                className="font-serif text-brief text-pretty"
              >
                {account.text}
              </MarginCited>
            ) : (
              NOT_FOUND
            )}
          </dd>
        </div>

        <div className={ROW}>
          <dt>
            <span className={TERM}>Injuries</span>
            {/* The way to the rest sits under the label, so no injury row wraps to make room for it. */}
            {groups.length > INJURIES_SHOWN && (
              <Link
                to={{ search: '?view=attorney' }}
                className="mt-0.5 block text-xs text-primary underline-offset-4 hover:underline"
              >
                All {groups.length} injuries
                <span className="sr-only"> on For Attorney</span>
              </Link>
            )}
          </dt>
          <dd className="min-w-0">
            {injuries.isPending && (
              <Loading label="Loading injuries">
                <Skeleton className="my-1.5 h-6" />
              </Loading>
            )}
            {injuries.isError && (
              <LoadError what="the injuries" error={injuries.error} onRetry={() => void injuries.refetch()} />
            )}
            {injuries.isSuccess &&
              (groups.length === 0 ? (
                NOT_FOUND
              ) : (
                <ul>
                  {shownInjuries.map(({ key, lead, facts }) => (
                    <MarginCited key={key} facts={facts} dense className="text-[15px]">
                      <span className="font-medium">{lead.title}</span>
                      <span className="text-muted-foreground">
                        {' · '}
                        {[KIND_LABELS[lead.kind], lead.value.body_part].filter(Boolean).join(' · ')}
                      </span>
                    </MarginCited>
                  ))}
                </ul>
              ))}
          </dd>
        </div>

        <div className={ROW}>
          <dt className={TERM}>Liability</dt>
          <dd className="min-w-0">
            {liability.isPending && (
              <Loading label="Loading liability">
                <Skeleton className="my-1.5 h-6" />
              </Loading>
            )}
            {liability.isError && (
              <LoadError what="the liability facts" error={liability.error} onRetry={() => void liability.refetch()} />
            )}
            {liability.isSuccess &&
              (leadingLiability ? (
                <MarginCited as="div" facts={[leadingLiability]} className="text-[15px]">
                  {leadingLiability.title}
                </MarginCited>
              ) : (
                NOT_FOUND
              ))}
          </dd>
        </div>
      </dl>
    </Section>
  )
}
