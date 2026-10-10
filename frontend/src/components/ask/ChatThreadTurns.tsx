import { useEffect, useMemo, useRef } from 'react'

import { ApiError } from '@/api/client'
import { useChatThread } from '@/api/chat'
import { ChatTurn } from '@/components/ask/ChatTurn'
import { LoadError } from '@/components/shared/LoadError'
import { Loading } from '@/components/shared/Loading'
import { Skeleton } from '@/components/ui/skeleton'
import { FrozenThreadContext } from '@/lib/frozenThread'

/**
 * A thread's turns, oldest first, polled while an answer is being written. When a turn
 * is added, the newest is scrolled into view. A closed thread's turns are the copy frozen
 * when it closed (D52), drawn the same way; their chips open the sources frozen with it
 * (D54), so a re-read since cannot change what they show. The Ask view and the side panel
 * both draw a thread through here.
 */
export function ChatThreadTurns({ matterId, threadId }: { matterId: number; threadId: number }) {
  const thread = useChatThread(matterId, threadId)
  const lastTurn = useRef<HTMLDivElement>(null)
  const turnCount = thread.data?.turns.length ?? 0
  const closed = thread.data?.closed_at != null
  const frozenThread = useMemo(() => (closed ? { threadId } : null), [closed, threadId])

  useEffect(() => {
    if (turnCount > 0) lastTurn.current?.scrollIntoView({ block: 'nearest' })
  }, [turnCount])

  if (thread.isPending) {
    return (
      <Loading label="Loading the thread" className="space-y-2 py-4">
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-5 w-full" />
        <Skeleton className="h-16 w-full" />
      </Loading>
    )
  }
  if (thread.isError) {
    if (thread.error instanceof ApiError && thread.error.status === 404) {
      return <p className="py-4 text-sm text-muted-foreground">This thread is not on this matter, or chat is not available.</p>
    }
    return (
      <div className="py-4">
        <LoadError what="the thread" error={thread.error} onRetry={() => void thread.refetch()} />
      </div>
    )
  }
  return (
    <FrozenThreadContext.Provider value={frozenThread}>
      <div className="divide-y">
        {thread.data.turns.map((turn, index) => (
          <div key={turn.turn_id} ref={index === turnCount - 1 ? lastTurn : undefined}>
            <ChatTurn matterId={matterId} turn={turn} closed={closed} />
          </div>
        ))}
      </div>
    </FrozenThreadContext.Provider>
  )
}
