import { RefreshCw } from 'lucide-react'

import { useDigestCost, useResync, type ResyncPhase } from '@/api/ops'
import type { MatterHeaderOut } from '@/api/types'
import { Button } from '@/components/ui/button'
import { formatDateTime, formatMicroDollars } from '@/lib/format'

const BUTTON_TEXT: Record<ResyncPhase, string> = {
  idle: 'Re-sync',
  syncing: 'Syncing from Clio…',
  digesting: 'Digesting…',
}

/** Proof the page is a live read of Clio: when it was synced, what the digest cost, and a re-sync. */
export function MatterFooter({ header }: { header: MatterHeaderOut }) {
  const cost = useDigestCost(header.matter_id)
  const resync = useResync()
  const sync = header.last_sync
  const failures = [
    header.last_sync?.error ? `sync: ${header.last_sync.error}` : null,
    header.last_digest?.error ? `digest: ${header.last_digest.error}` : null,
  ].filter((failure): failure is string => failure !== null)

  return (
    <footer className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-2 border-t pt-4 text-sm text-muted-foreground">
      <span className="tabular-nums">
        {sync?.finished_at
          ? `Synced from Clio ${formatDateTime(sync.finished_at)}`
          : sync
            ? 'A sync has started but not finished'
            : 'Not synced from Clio yet'}
      </span>
      <span className="tabular-nums">
        {cost.isSuccess &&
          `Digest cost ${formatMicroDollars(cost.data.cost_micro_usd)} (${cost.data.model_calls} model calls, ${cost.data.cache_hits} answered from cache)`}
        {cost.isError && 'Digest cost unavailable'}
      </span>
      {failures.length > 0 && (
        <span role="alert" className="font-medium text-danger">
          The last {failures.join('; ')}
        </span>
      )}
      <div className="ml-auto flex items-center gap-3">
        {resync.isError && (
          <span role="alert" className="text-danger">
            {resync.error.message}
          </span>
        )}
        <Button variant="outline" size="sm" onClick={() => resync.mutate()} disabled={resync.isPending}>
          <RefreshCw aria-hidden />
          {BUTTON_TEXT[resync.phase]}
        </Button>
      </div>
    </footer>
  )
}
