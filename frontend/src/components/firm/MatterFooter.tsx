import { RefreshCw, RotateCcw } from 'lucide-react'
import { useId } from 'react'

import { useDigestCost, useJobStatus, useResync, useRetryFailedCalls, type ResyncPhase } from '@/api/ops'
import type { MatterHeaderOut, RunOut, RunStatusOut } from '@/api/types'
import { Button } from '@/components/ui/button'
import { formatDateTime, formatMicroDollars } from '@/lib/format'

const BUTTON_TEXT: Record<ResyncPhase, string> = {
  idle: 'Re-sync',
  syncing: 'Syncing from Clio…',
  digesting: 'Digesting…',
}

/**
 * Per-item failures a run carried on past, such as one endpoint refused or one file not
 * downloaded. The pipeline lists them in `stats.errors`; the run's own `error` is only
 * set when the whole run stopped.
 */
function itemErrors(run: RunOut | null): string[] {
  const errors = run?.stats?.errors
  return Array.isArray(errors) ? errors.filter((error): error is string => typeof error === 'string') : []
}

function failureText(label: string, run: RunOut | null): string | null {
  if (!run) return null
  if (run.error) return `The last ${label} stopped: ${run.error}`
  const skipped = itemErrors(run)
  if (skipped.length === 0) return null
  const items = skipped.length === 1 ? '1 item' : `${skipped.length} items`
  return `The last ${label} skipped ${items}: ${skipped[0]}${skipped.length > 1 ? '; …' : ''}`
}

/** A failure before the job's run began, which no run row records. */
function startFailureText(label: string, status: RunStatusOut | undefined): string | null {
  const failure = status?.start_failure
  return failure ? `The last ${label} could not start: ${failure.error}` : null
}

/** Proof the page is a live read of Clio: when it was synced, what the digest cost, and a re-sync. */
export function MatterFooter({ header }: { header: MatterHeaderOut }) {
  const cost = useDigestCost(header.matter_id)
  const syncStatus = useJobStatus('sync')
  const digestStatus = useJobStatus('digest')
  const resync = useResync()
  const retry = useRetryFailedCalls()
  const costNoteId = useId()
  // The server counts the calls a digest would answer from the cache as failed (D29).
  const failedCalls = digestStatus.data?.cached_failed_calls ?? 0
  const busy = resync.isPending || retry.isPending
  const sync = header.last_sync
  const failures = [
    { text: startFailureText('sync', syncStatus.data), detail: [] },
    { text: failureText('sync', header.last_sync), detail: itemErrors(header.last_sync) },
    { text: startFailureText('digest', digestStatus.data), detail: [] },
    { text: failureText('digest', header.last_digest), detail: itemErrors(header.last_digest) },
  ].filter((failure) => failure.text !== null)

  return (
    <footer className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-2 border-t pt-4 text-sm text-muted-foreground">
      {/* Announced when a re-sync or digest finishes and the line changes. */}
      <span role="status" className="flex flex-wrap gap-x-6 gap-y-2">
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
      </span>
      {failures.map((failure) => (
        <span
          key={failure.text}
          role="alert"
          className="font-medium text-danger"
          title={failure.detail.length > 1 ? failure.detail.join('\n') : undefined}
        >
          {failure.text}
        </span>
      ))}
      {/* Wraps on a narrow screen, so its buttons never push the page wider than the viewport. */}
      <div className="ml-auto flex min-w-0 flex-wrap items-center gap-3">
        {resync.isError && (
          <span role="alert" className="text-danger">
            {resync.error.message}
          </span>
        )}
        {retry.isError && (
          <span role="alert" className="text-danger">
            {retry.error.message}
          </span>
        )}
        {(failedCalls > 0 || retry.isPending) && (
          <>
            <span id={costNoteId} className="text-xs">
              Retrying asks the model again, which costs money.
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => retry.mutate()}
              disabled={busy}
              aria-describedby={costNoteId}
            >
              <RotateCcw aria-hidden />
              {retry.isPending
                ? BUTTON_TEXT.digesting
                : `Retry ${failedCalls} failed ${failedCalls === 1 ? 'call' : 'calls'}`}
            </Button>
          </>
        )}
        <Button variant="outline" size="sm" onClick={() => resync.mutate()} disabled={busy}>
          <RefreshCw aria-hidden />
          {BUTTON_TEXT[resync.phase]}
        </Button>
      </div>
    </footer>
  )
}
