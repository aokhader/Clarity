import { useId } from 'react'

import { useChatThreads } from '@/api/chat'
import { ChatThreadRow } from '@/components/ask/ChatThreadRow'
import { LoadError } from '@/components/shared/LoadError'
import { Loading } from '@/components/shared/Loading'
import { Skeleton } from '@/components/ui/skeleton'

type ChatThreadListProps = {
  matterId: number
  /** A thread was closed from the list (D52). */
  onClosed: (threadId: number) => void
}

/**
 * The matter's threads in two groups, Open and Closed (D52), each in the order the server
 * gives: open ones by their last question, closed ones by when they closed, newest first.
 * The Closed group shows once a thread has been closed.
 */
export function ChatThreadList({ matterId, onClosed }: ChatThreadListProps) {
  const threads = useChatThreads(matterId)
  const groupId = useId()

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
  const groups = [
    { name: 'Open', threads: threads.data.filter((thread) => thread.closed_at == null) },
    { name: 'Closed', threads: threads.data.filter((thread) => thread.closed_at != null) },
  ].filter((group) => group.name === 'Open' || group.threads.length > 0)

  return (
    <div className="space-y-5">
      {groups.map((group) => (
        <section key={group.name} aria-labelledby={`${groupId}-${group.name}`}>
          <h3
            id={`${groupId}-${group.name}`}
            className="mb-1.5 text-xs font-semibold tracking-wider text-muted-foreground uppercase"
          >
            {group.name}
          </h3>
          {group.threads.length === 0 ? (
            <p className="text-sm text-muted-foreground">No open questions.</p>
          ) : (
            <ul className="divide-y border-t">
              {group.threads.map((thread) => (
                <ChatThreadRow key={thread.thread_id} matterId={matterId} thread={thread} onClosed={onClosed} />
              ))}
            </ul>
          )}
        </section>
      ))}
    </div>
  )
}
