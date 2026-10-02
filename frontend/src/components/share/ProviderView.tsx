import type { ProviderItemOut, ProviderPayload } from '@/api/types'
import { CoverageSection } from '@/components/share/CoverageSection'
import { ProviderHeader } from '@/components/share/ProviderHeader'
import { ProviderItemList } from '@/components/share/ProviderItemList'
import { StatusTracker } from '@/components/share/StatusTracker'
import { UpdatesList } from '@/components/share/UpdatesList'
import { Panel } from '@/components/shared/Panel'
import { formatDate, formatMonth } from '@/lib/format'

type ProviderViewProps = {
  payload: ProviderPayload
  /** Opens the cited page of a bill or record. Absent in the firm's preview. */
  onOpenSource?: (item: ProviderItemOut) => void
}

/**
 * What a provider sees, rendered from the payload alone. The share composer's preview
 * uses this same component. A section whose setting is off is null and is left out,
 * with no placeholder.
 */
export function ProviderView({ payload, onOpenSource }: ProviderViewProps) {
  const { status, coverage, requests, bills, records, treatment_activity, updates } = payload
  return (
    <div className="space-y-4">
      <ProviderHeader payload={payload} />
      {status && <StatusTracker status={status} />}
      {coverage && <CoverageSection coverage={coverage} />}
      {requests && (
        <Panel title="What the firm needs from your office">
          <ProviderItemList items={requests} empty="Nothing outstanding from your office." />
        </Panel>
      )}
      {(bills || records) && (
        <Panel title="Your bills and records on file">
          <div className="space-y-4">
            {bills && (
              <section aria-label="Bills">
                <h3 className="text-sm font-medium">Bills</h3>
                <ProviderItemList items={bills} empty="No bills from your office on file." onOpenSource={onOpenSource} />
              </section>
            )}
            {records && (
              <section aria-label="Records">
                <h3 className="text-sm font-medium">Records</h3>
                <ProviderItemList
                  items={records}
                  empty="No records from your office on file."
                  onOpenSource={onOpenSource}
                />
              </section>
            )}
          </div>
        </Panel>
      )}
      {treatment_activity && (
        <Panel title="Treatment activity">
          <p className="text-sm">
            Most recent treatment visit on file: <span className="font-medium">{formatMonth(treatment_activity.last_visit_month)}</span>
          </p>
        </Panel>
      )}
      {updates && (
        <Panel title="Recent updates">
          <UpdatesList updates={updates} />
        </Panel>
      )}
      {payload.note && (
        <Panel title="Note from the firm">
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
