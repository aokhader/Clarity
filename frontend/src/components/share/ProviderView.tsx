import type { ProviderItemOut, ProviderPayload } from '@/api/types'
import { BillsTotal } from '@/components/share/BillsTotal'
import { CoverageSection } from '@/components/share/CoverageSection'
import { ProviderHeader } from '@/components/share/ProviderHeader'
import { ProviderItemList } from '@/components/share/ProviderItemList'
import { StatusTracker } from '@/components/share/StatusTracker'
import { UpdatesList } from '@/components/share/UpdatesList'
import { Panel } from '@/components/shared/Panel'
import { formatDate, formatMonth } from '@/lib/format'

/** Bills and records each show this many rows and scroll the rest. */
const VISIBLE_ITEMS = 10

type ProviderViewProps = {
  payload: ProviderPayload
  /** Opens the cited page of a bill or record: the provider's page viewer, or the firm's drawer in a preview. */
  onOpenSource?: (item: ProviderItemOut) => void
  /** 1 on the provider's own page; 2 in a firm page's preview, under that page's h1. */
  headingLevel?: 1 | 2
}

/**
 * What a provider sees, rendered from the payload alone. The share composer's preview
 * uses this same component. A section whose setting is off is null and is left out,
 * with no placeholder.
 */
export function ProviderView({ payload, onOpenSource, headingLevel = 1 }: ProviderViewProps) {
  const { status, coverage, requests, bills, records, treatment_activity, updates } = payload
  const sharesNothing =
    [status, coverage, requests, bills, records, treatment_activity, updates].every((section) => section === null) &&
    !payload.note
  const listsLien = bills?.some((item) => item.kind === 'lien') ?? false
  const billsHeading = listsLien ? 'Bills and liens' : 'Bills'
  const level = headingLevel === 1 ? 2 : 3
  const Subheading = headingLevel === 1 ? 'h3' : 'h4'
  return (
    <div className="space-y-4">
      <ProviderHeader payload={payload} level={headingLevel} />
      {sharesNothing && (
        <p className="text-sm text-muted-foreground">The firm has not shared any case details on this link.</p>
      )}
      {status && <StatusTracker status={status} level={level} />}
      {coverage && <CoverageSection coverage={coverage} level={level} />}
      {requests && (
        <Panel title="What the firm needs from your office" level={level}>
          <ProviderItemList items={requests} empty="Nothing outstanding from your office." />
        </Panel>
      )}
      {(bills || records) && (
        <Panel title="Your bills and records on file" level={level}>
          <div className="space-y-4">
            {payload.bills_total && <BillsTotal total={payload.bills_total} />}
            {bills && (
              // The bills setting releases liens as well as bills, and the total above counts
              // bills only (BillsTotal). A listed lien is labelled on its row, and the caption
              // says it is not one of the total's addends.
              <section aria-label={billsHeading}>
                <Subheading className="text-sm font-medium">{billsHeading}</Subheading>
                {listsLien && payload.bills_total && (
                  <p className="mt-0.5 text-xs text-muted-foreground">Liens are listed, but not added to the total above.</p>
                )}
                <ProviderItemList
                  items={bills}
                  empty="No bills from your office on file."
                  onOpenSource={onOpenSource}
                  scroll={{ rows: VISIBLE_ITEMS, label: `${billsHeading}, scrollable` }}
                />
              </section>
            )}
            {records && (
              <section aria-label="Records">
                <Subheading className="text-sm font-medium">Records</Subheading>
                <ProviderItemList
                  items={records}
                  empty="No records from your office on file."
                  onOpenSource={onOpenSource}
                  scroll={{ rows: VISIBLE_ITEMS, label: 'Records, scrollable' }}
                />
              </section>
            )}
          </div>
        </Panel>
      )}
      {treatment_activity && (
        <Panel title="Treatment activity" level={level}>
          <p className="text-sm">
            Most recent treatment visit on file: <span className="font-medium">{formatMonth(treatment_activity.last_visit_month)}</span>
          </p>
        </Panel>
      )}
      {updates && (
        <Panel title="Recent updates" level={level}>
          <UpdatesList updates={updates} />
        </Panel>
      )}
      {payload.note && (
        <Panel title="Note from the firm" level={level}>
          <p className="whitespace-pre-line font-serif text-base leading-relaxed">{payload.note}</p>
        </Panel>
      )}
      <p className="pt-2 text-xs text-muted-foreground">
        Shared by the firm on {formatDate(payload.shared_on)}
        {payload.expires_on && <>. This link stops working after {formatDate(payload.expires_on)}</>}.
      </p>
    </div>
  )
}
