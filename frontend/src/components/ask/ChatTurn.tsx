import { useId } from 'react'

import { useRetryTurn } from '@/api/chat'
import type { ChatTurnOut, ChatTurnStatus } from '@/api/types'
import { useFirmUser } from '@/api/users'
import { AskItemChip } from '@/components/ask/AskItemChip'
import { ChatAnswer } from '@/components/ask/ChatAnswer'
import { SourceChipList } from '@/components/shared/SourceChipList'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { askErrorText } from '@/lib/chatErrors'
import { formatDateTime, formatMicroDollars } from '@/lib/format'

/** Said to screen readers when a turn's state changes, from the one region that stays put. */
const STATUS_WORDS: Record<ChatTurnStatus, string> = {
  running: 'Reading the file…',
  done: 'Answer ready.',
  failed: 'The answer could not be written.',
  no_model: 'Chat isn’t configured.',
}

type ChatTurnProps = {
  matterId: number
  turn: ChatTurnOut
  /** The turn belongs to a closed thread (D52): a record as it read then, so no Retry. */
  closed?: boolean
}

/**
 * One question and its answer: who asked and when, the items pointed at with their
 * sources, then the answer by its state. The answer arrives whole, after the server has
 * checked every sentence's citations, so a running turn shows only that it is reading.
 */
export function ChatTurn({ matterId, turn, closed = false }: ChatTurnProps) {
  const questionId = useId()
  const retry = useRetryTurn(matterId)
  const user = useFirmUser()
  const retryButton = !closed && (
    <Button
      variant="outline"
      size="xs"
      disabled={user === null || retry.isPending}
      onClick={() => user && retry.mutate({ userId: user.id, turnId: turn.turn_id })}
    >
      Retry
    </Button>
  )

  return (
    <article aria-labelledby={questionId} className="py-4">
      <p className="text-xs text-muted-foreground">
        {turn.asked_by ?? 'A firm user'} asked · <time dateTime={turn.asked_at}>{formatDateTime(turn.asked_at)}</time>
      </p>
      <h3 id={questionId} className="mt-0.5 text-[15px] font-semibold text-pretty [overflow-wrap:anywhere]">
        {turn.question}
      </h3>
      {turn.items.length > 0 && (
        <ul aria-label="Items pointed at" className="mt-2 flex flex-wrap gap-1.5">
          {turn.items.map((item, index) => (
            <li key={index} className="max-w-full">
              <AskItemChip label={item.label}>
                <SourceChipList facts={item.facts} max={2} />
              </AskItemChip>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-3">
        <p role="status" className="sr-only">
          {STATUS_WORDS[turn.status]}
        </p>
        {turn.status === 'running' && (
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">Reading the file…</p>
            <div aria-hidden className="space-y-2">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-11/12" />
              <Skeleton className="h-4 w-2/3" />
            </div>
          </div>
        )}
        {turn.status === 'done' && <ChatAnswer turn={turn} />}
        {turn.status === 'failed' && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-danger/40 bg-danger-soft px-3 py-2 text-sm">
            <span>
              The answer could not be written.{' '}
              {turn.error && <span className="text-muted-foreground">{turn.error}</span>}
            </span>
            {retryButton}
          </div>
        )}
        {turn.status === 'no_model' && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-input px-3 py-2 text-sm">
            <span>
              Chat isn&apos;t configured. Set <code>CHAT_MODEL</code>, <code>CHAT_PRICE_IN</code> and{' '}
              <code>CHAT_PRICE_OUT</code> in <code>.env</code>.
            </span>
            {retryButton}
          </div>
        )}
        {retry.isError && (
          <p role="alert" className="mt-2 text-sm text-danger">
            {askErrorText(retry.error, closed)}
          </p>
        )}
      </div>

      {turn.status === 'done' && (
        <p className="mt-2 text-xs text-muted-foreground tabular-nums">
          {turn.answered_at && <>Answered {formatDateTime(turn.answered_at)} · </>}
          {turn.cost_micro_usd !== null ? `cost ${formatMicroDollars(turn.cost_micro_usd)}` : 'from the cache, no cost'}
        </p>
      )}
    </article>
  )
}
