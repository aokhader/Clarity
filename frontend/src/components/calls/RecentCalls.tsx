import { History } from 'lucide-react'

import { useMatterCalls } from '@/api/calls'
import type { NotesStatus } from '@/api/types'
import { LoadError } from '@/components/shared/LoadError'
import { Panel } from '@/components/shared/Panel'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDateTime } from '@/lib/format'

const NOTES_TEXT: Record<NotesStatus, string> = {
  not_started: 'On the call',
  running: 'Writing notes',
  done: 'Notes ready',
  failed: 'Notes failed',
  no_model: 'Transcript only',
}

type RecentCallsProps = {
  matterId: number
  /** The call whose notes are open, if any. */
  openCallId: number | null
  onOpen: (callId: number) => void
}

/** Calls placed from Clarity on this matter, newest first, each opening its notes. */
export function RecentCalls({ matterId, openCallId, onOpen }: RecentCallsProps) {
  const calls = useMatterCalls(matterId)
  if (calls.isSuccess && calls.data.length === 0) return null
  return (
    <Panel title="Recent calls" icon={<History />}>
      {calls.isPending && <Skeleton className="h-16 w-full" aria-label="Loading recent calls" />}
      {calls.isError && <LoadError what="recent calls" error={calls.error} onRetry={() => void calls.refetch()} />}
      {calls.isSuccess && (
        <ul className="-my-2 divide-y">
          {calls.data.map((call) => (
            <li key={call.call_id} className="flex items-center justify-between gap-3 py-2 text-sm">
              <div className="min-w-0">
                <p className="font-medium">{call.target.name ?? 'Name not in file'}</p>
                <p className="text-xs text-muted-foreground tabular-nums">
                  {formatDateTime(call.started_at)} · {NOTES_TEXT[call.notes_status]}
                </p>
              </div>
              {call.ended_at !== null && (
                <Button
                  variant={call.call_id === openCallId ? 'default' : 'outline'}
                  size="xs"
                  aria-pressed={call.call_id === openCallId}
                  onClick={() => onOpen(call.call_id)}
                >
                  Notes
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}
