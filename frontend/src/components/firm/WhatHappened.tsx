import { Link } from 'react-router'

import { useMatterInjuries, useMatterTimeline } from '@/api/matters'
import type { IncidentAccountOut } from '@/api/types'
import { MarginCited } from '@/components/firm/MarginCited'
import { LoadError } from '@/components/shared/LoadError'
import { Loading } from '@/components/shared/Loading'
import { Section } from '@/components/shared/Section'
import { Skeleton } from '@/components/ui/skeleton'
import { groupInjuriesByRegion, isInjury, topBySignificance } from '@/lib/facts'
import { KIND_LABELS } from '@/lib/labels'

/** Body regions on the Overview; every injury is listed on For Attorney. */
const REGIONS_SHOWN = 3
/** Two liability facts, so a contested point never reads as settled by one opinion (D40). */
const LIABILITY_SHOWN = 2

/** One term and its value: a fixed label column, then the value with its chips in the margin. */
const ROW = 'grid grid-cols-1 items-baseline gap-x-4 @min-[40rem]:grid-cols-[7rem_minmax(0,1fr)]'
const TERM = 'text-xs font-semibold tracking-wider text-muted-foreground uppercase'
const NOT_FOUND = <p className="py-1.5 text-[15px] text-muted-foreground">Not found in file</p>

/**
 * What the case is about, as a definition list: the incident as the records describe it
 * (never the date field, D39), the injured body regions the most records state, and the
 * two weightiest liability facts (D40). Each value cites its sources in the margin.
 */
export function WhatHappened({ matterId, account }: { matterId: number; account: IncidentAccountOut | null }) {
  const injuries = useMatterInjuries(matterId)
  const liability = useMatterTimeline(matterId, 'liability', '')
  const regions = groupInjuriesByRegion(injuries.data?.filter(isInjury) ?? []).slice(0, REGIONS_SHOWN)
  const leadingLiability = topBySignificance(liability.data, LIABILITY_SHOWN)

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
                className="text-base leading-relaxed text-pretty"
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
            {/* The way to the rest sits under the label, so no injury row wraps to make room for it.
                No count: the records restate one injury many times over (D40). */}
            {regions.length > 0 && (
              <Link
                to={{ search: '?view=attorney' }}
                className="mt-0.5 block text-xs text-primary underline-offset-4 hover:underline"
              >
                All injuries on For Attorney
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
              (regions.length === 0 ? (
                NOT_FOUND
              ) : (
                <ul>
                  {regions.map(({ region, lead, facts }) => (
                    <MarginCited key={region} facts={facts} dense className="text-[15px]">
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
              (leadingLiability.length === 0 ? (
                NOT_FOUND
              ) : (
                <ul>
                  {leadingLiability.map((fact) => (
                    <MarginCited key={fact.id} facts={[fact]} dense className="text-[15px]">
                      {fact.title}
                    </MarginCited>
                  ))}
                </ul>
              ))}
          </dd>
        </div>
      </dl>
    </Section>
  )
}
