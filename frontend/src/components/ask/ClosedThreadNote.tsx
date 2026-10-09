import { transcriptUrl } from '@/api/chat'
import type { ChatThreadOut } from '@/api/types'
import { Button } from '@/components/ui/button'
import { formatDateTime } from '@/lib/format'

type ClosedThreadNoteProps = {
  matterId: number
  thread: ChatThreadOut
  /** Leave the closed thread for a fresh one, and put focus where the question is written. */
  onNewQuestion: () => void
}

/**
 * What a closed thread shows in place of the composer (D52): when and by whom it was
 * closed, its text transcript to download, and a way to ask afresh. Neutral, since a
 * closed thread is a record kept, not a warning. It has no frame of its own; where it
 * sits, a hairline sets it off.
 */
export function ClosedThreadNote({ matterId, thread, onNewQuestion }: ClosedThreadNoteProps) {
  if (thread.closed_at == null) return null
  return (
    <div className="space-y-2 text-sm">
      <p className="text-pretty">
        Closed <time dateTime={thread.closed_at}>{formatDateTime(thread.closed_at)}</time> by{' '}
        {thread.closed_by ?? 'a firm user'}. This is the transcript as it read then.
      </p>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <a
          href={transcriptUrl(matterId, thread.thread_id)}
          download
          className="text-primary underline-offset-4 hover:underline"
        >
          Download transcript
        </a>
        <Button variant="outline" size="xs" onClick={onNewQuestion}>
          New question
        </Button>
      </div>
    </div>
  )
}
