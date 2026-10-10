import { useRef } from 'react'

import { useChatThread } from '@/api/chat'
import { ChatComposer } from '@/components/ask/ChatComposer'
import { ChatThreadList } from '@/components/ask/ChatThreadList'
import { ChatThreadTurns } from '@/components/ask/ChatThreadTurns'
import { ClosedThreadNote } from '@/components/ask/ClosedThreadNote'
import { Panel } from '@/components/shared/Panel'
import { Button } from '@/components/ui/button'
import { useAskContext } from '@/lib/askState'

/**
 * The Ask view (`?view=ask`, D49): the matter's threads, and the chosen one at full width
 * with its composer. It shares the panel's thread and question, so "Open in Ask view"
 * carries on where the panel was; the panel and the Ask bar are hidden here. A closed
 * thread (D52) opens read-only: its frozen turns, when it was closed, and its transcript.
 */
export function AskView({ matterId }: { matterId: number }) {
  const ask = useAskContext()
  const thread = useChatThread(matterId, ask.threadId)
  const heading = useRef<HTMLHeadingElement>(null)
  const body = useRef<HTMLDivElement>(null)
  const title = ask.threadId === null ? 'New question' : (thread.data?.title ?? 'Question')
  const closedThread = thread.data?.closed_at != null ? thread.data : null
  // The composer waits for the thread, so a closed one never offers a follow-up; it
  // shows nothing on a closed thread but a refusal, and the note stands in for it.
  const loaded = ask.threadId === null || thread.data !== undefined

  const startNewQuestion = () => {
    ask.newQuestion()
    // The button pressed goes with the thread, so focus moves to the question box.
    requestAnimationFrame(() => body.current?.querySelector('textarea')?.focus())
  }
  const showClosed = (threadId: number) => {
    ask.setThreadId(threadId)
    requestAnimationFrame(() => heading.current?.focus())
  }

  return (
    <div className="grid grid-cols-1 items-start gap-6 xl:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
      <Panel title="Questions on this matter">
        <ChatThreadList matterId={matterId} onClosed={showClosed} />
      </Panel>
      <Panel
        title={title}
        headingRef={heading}
        actions={
          ask.threadId !== null &&
          closedThread === null && (
            <Button variant="outline" size="xs" onClick={startNewQuestion}>
              New question
            </Button>
          )
        }
      >
        <div ref={body}>
          {closedThread !== null && (
            <div className="border-b pb-3">
              <ClosedThreadNote matterId={matterId} thread={closedThread} onNewQuestion={startNewQuestion} />
            </div>
          )}
          {ask.threadId !== null && (
            <div className={loaded && closedThread === null ? 'mb-4 border-b' : undefined}>
              <ChatThreadTurns matterId={matterId} threadId={ask.threadId} />
            </div>
          )}
          {ask.threadId === null && (
            <p className="mb-4 text-sm text-muted-foreground">
              Ask about this matter. Each sentence of the answer comes with its sources; what the file does not answer
              is said plainly.
            </p>
          )}
          {loaded && <ChatComposer matterId={matterId} />}
        </div>
      </Panel>
    </div>
  )
}
