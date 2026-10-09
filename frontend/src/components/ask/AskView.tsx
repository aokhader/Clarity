import { useChatThread } from '@/api/chat'
import { ChatComposer } from '@/components/ask/ChatComposer'
import { ChatThreadList } from '@/components/ask/ChatThreadList'
import { ChatThreadTurns } from '@/components/ask/ChatThreadTurns'
import { Panel } from '@/components/shared/Panel'
import { Button } from '@/components/ui/button'
import { useAskContext } from '@/lib/askState'

/**
 * The Ask view (`?view=ask`, D49): the matter's threads, and the chosen one at full width
 * with its composer. It shares the panel's thread and question, so "Open in Ask view"
 * carries on where the panel was; the panel and the Ask bar are hidden here.
 */
export function AskView({ matterId }: { matterId: number }) {
  const ask = useAskContext()
  const thread = useChatThread(matterId, ask.threadId)
  const title = ask.threadId === null ? 'New question' : (thread.data?.title ?? 'Question')
  return (
    <div className="grid grid-cols-1 items-start gap-6 xl:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
      <Panel title="Questions on this matter">
        <ChatThreadList matterId={matterId} />
      </Panel>
      <Panel
        title={title}
        actions={
          ask.threadId !== null && (
            <Button variant="outline" size="xs" onClick={ask.newQuestion}>
              New question
            </Button>
          )
        }
      >
        {ask.threadId !== null && (
          <div className="mb-4 border-b">
            <ChatThreadTurns matterId={matterId} threadId={ask.threadId} />
          </div>
        )}
        {ask.threadId === null && (
          <p className="mb-4 text-sm text-muted-foreground">
            Ask about this matter. Each sentence of the answer comes with its sources; what the file does not answer
            is said plainly.
          </p>
        )}
        <ChatComposer matterId={matterId} />
      </Panel>
    </div>
  )
}
