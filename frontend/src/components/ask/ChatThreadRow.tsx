import { useEffect, useId, useRef, useState } from 'react'

import { useCloseThread } from '@/api/chat'
import type { ChatThreadSummaryOut, ChatTurnStatus } from '@/api/types'
import { useFirmUser } from '@/api/users'
import { Button } from '@/components/ui/button'
import { useAskContext } from '@/lib/askState'
import { closeErrorText } from '@/lib/chatErrors'
import { formatCount, formatDateTime } from '@/lib/format'
import { cn } from '@/lib/utils'

const STATUS_TEXT: Record<ChatTurnStatus, string> = {
  running: 'Answering',
  done: 'Answered',
  failed: 'Failed',
  no_model: 'Not configured',
}

type ChatThreadRowProps = {
  matterId: number
  thread: ChatThreadSummaryOut
  /** The thread was closed from this row; the view opens it read-only and takes focus. */
  onClosed: (threadId: number) => void
}

/**
 * One thread in the list: choosing it opens it. An open thread can be closed (D52), which
 * asks once in place, since a closed thread takes no more questions; a closed one says
 * when it was closed.
 */
export function ChatThreadRow({ matterId, thread, onClosed }: ChatThreadRowProps) {
  const ask = useAskContext()
  const user = useFirmUser()
  const close = useCloseThread(matterId)
  const [confirming, setConfirming] = useState(false)
  const closeButton = useRef<HTMLButtonElement>(null)
  const cancelButton = useRef<HTMLButtonElement>(null)
  const questionId = useId()
  const chosen = thread.thread_id === ask.threadId
  const closed = thread.closed_at != null

  // The question takes focus when it appears, on its safe answer.
  useEffect(() => {
    if (confirming) cancelButton.current?.focus()
  }, [confirming])

  const cancel = () => {
    setConfirming(false)
    close.reset()
    requestAnimationFrame(() => closeButton.current?.focus())
  }

  const confirm = () => {
    if (user === null) return
    close.mutate(
      { userId: user.id, threadId: thread.thread_id },
      {
        onSuccess: () => {
          setConfirming(false)
          onClosed(thread.thread_id)
        },
      },
    )
  }

  return (
    <li
      className={cn('border-l-3 py-2.5 pr-1 pl-3', chosen ? 'border-primary bg-muted' : 'border-transparent')}
    >
      <div className="flex items-start gap-2">
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
            {thread.closed_at != null ? (
              <>
                Closed {formatDateTime(thread.closed_at)} · {thread.asked_by ?? 'A firm user'} asked ·{' '}
                {formatCount(thread.turn_count, 'question')}
              </>
            ) : (
              <>
                {thread.asked_by ?? 'A firm user'} · {formatDateTime(thread.updated_at)} ·{' '}
                {formatCount(thread.turn_count, 'question')} · {STATUS_TEXT[thread.last_status]}
              </>
            )}
          </span>
        </button>
        {!closed && !confirming && (
          <Button
            ref={closeButton}
            variant="ghost"
            size="xs"
            disabled={user === null}
            aria-label={`Close ${thread.title}`}
            onClick={() => setConfirming(true)}
          >
            Close
          </Button>
        )}
      </div>
      {confirming && (
        <div
          role="group"
          aria-labelledby={questionId}
          onKeyDown={(event) => {
            if (event.key === 'Escape') {
              event.preventDefault()
              cancel()
            }
          }}
          className="mt-2 border-t pt-2"
        >
          <p id={questionId} className="text-sm">
            Close this thread? It keeps a transcript and takes no more questions.
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            <Button size="xs" disabled={user === null || close.isPending} onClick={confirm}>
              {close.isPending ? 'Closing…' : 'Close'}
            </Button>
            <Button ref={cancelButton} variant="outline" size="xs" onClick={cancel}>
              Cancel
            </Button>
          </div>
          {close.isError && (
            <p role="alert" className="mt-2 text-sm text-danger">
              {closeErrorText(close.error)}
            </p>
          )}
        </div>
      )}
    </li>
  )
}
