import { useArchiveThread, useChatThreads } from '@/api/chat'
import type { ChatTurnStatus } from '@/api/types'
import { useFirmUser } from '@/api/users'
import { LoadError } from '@/components/shared/LoadError'
import { Loading } from '@/components/shared/Loading'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useAskContext } from '@/lib/askState'
import { formatCount, formatDateTime } from '@/lib/format'
import { cn } from '@/lib/utils'

const STATUS_TEXT: Record<ChatTurnStatus, string> = {
  running: 'Answering',
  done: 'Answered',
  failed: 'Failed',
  no_model: 'Not configured',
}

/** The matter's threads, newest first; choosing one opens it, and Archive takes it off the list. */
export function ChatThreadList({ matterId }: { matterId: number }) {
  const ask = useAskContext()
  const threads = useChatThreads(matterId)
  const archive = useArchiveThread(matterId)
  const user = useFirmUser()

  if (threads.isPending) {
    return (
      <Loading label="Loading the questions" className="space-y-3">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-2/3" />
      </Loading>
    )
  }
  if (threads.isError) {
    return <LoadError what="the questions" error={threads.error} onRetry={() => void threads.refetch()} />
  }
  if (threads.data.length === 0) {
    return <p className="text-sm text-muted-foreground">No questions asked on this matter yet.</p>
  }
  return (
    <>
      <ul className="-my-1 divide-y">
        {threads.data.map((thread) => {
          const chosen = thread.thread_id === ask.threadId
          return (
            <li
              key={thread.thread_id}
              className={cn('flex items-start gap-2 border-l-3 py-2.5 pr-1 pl-3', chosen ? 'border-primary bg-muted' : 'border-transparent')}
            >
              <button
                type="button"
                aria-current={chosen ? 'true' : undefined}
                onClick={() => ask.setThreadId(thread.thread_id)}
                className="min-w-0 flex-1 text-left"
              >
                <span className="block text-[15px] font-medium [overflow-wrap:anywhere] hover:text-primary">
                  {thread.title}
                </span>
                <span className="block text-xs text-muted-foreground tabular-nums">
                  {thread.asked_by ?? 'A firm user'} · {formatDateTime(thread.updated_at)} ·{' '}
                  {formatCount(thread.turn_count, 'question')} · {STATUS_TEXT[thread.last_status]}
                </span>
              </button>
              <Button
                variant="ghost"
                size="xs"
                disabled={user === null || archive.isPending}
                aria-label={`Archive ${thread.title}`}
                onClick={() =>
                  user &&
                  archive.mutate(
                    { userId: user.id, threadId: thread.thread_id },
                    { onSuccess: () => chosen && ask.setThreadId(null) },
                  )
                }
              >
                Archive
              </Button>
            </li>
          )
        })}
      </ul>
      {archive.isError && (
        <p role="alert" className="mt-2 text-sm text-danger">
          Could not archive the thread. {archive.error.message}
        </p>
      )}
    </>
  )
}
