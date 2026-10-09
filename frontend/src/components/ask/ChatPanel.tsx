import { X } from 'lucide-react'
import { useEffect, useId, useRef } from 'react'
import { Link } from 'react-router'

import { useChatThread } from '@/api/chat'
import { ChatComposer } from '@/components/ask/ChatComposer'
import { ChatThreadTurns } from '@/components/ask/ChatThreadTurns'
import { ClosedThreadNote } from '@/components/ask/ClosedThreadNote'
import { Button } from '@/components/ui/button'
import { ASK_PANEL_ATTRIBUTE, useAskContext } from '@/lib/askState'
import { cn } from '@/lib/utils'

/**
 * The thread beside the page (D49). It is not a dialog: the page stays usable, and a
 * chip in it opens the source drawer, which hands focus back to the chip. From xl up it
 * is the page's third column, sticky and full height; narrower, it lies over the right
 * of the page, under the drawer, and steps aside while an item is being picked so the
 * rows can be seen. Escape closes it and returns focus to what opened it. A closed thread
 * (D52) is read-only: where the composer was, it says when it was closed.
 */
export function ChatPanel({ matterId }: { matterId: number }) {
  const ask = useAskContext()
  const headingId = useId()
  const heading = useRef<HTMLHeadingElement>(null)
  const footer = useRef<HTMLDivElement>(null)
  const thread = useChatThread(matterId, ask.threadId)
  const closedThread = thread.data?.closed_at != null ? thread.data : null
  // The composer waits for the thread, so a closed one never offers a follow-up; it
  // shows nothing on a closed thread but a refusal, and the note stands in for it.
  const loaded = ask.threadId === null || thread.data !== undefined
  const { panelWantsFocus, panelFocused } = ask

  const startNewQuestion = () => {
    ask.newQuestion()
    // The button pressed goes with the thread, so focus moves to the question box.
    requestAnimationFrame(() => footer.current?.querySelector('textarea')?.focus())
  }

  useEffect(() => {
    if (!panelWantsFocus) return
    heading.current?.focus()
    panelFocused()
  }, [panelWantsFocus, panelFocused])

  return (
    <aside
      {...{ [ASK_PANEL_ATTRIBUTE]: '' }}
      aria-labelledby={headingId}
      onKeyDown={(event) => {
        if (event.key === 'Escape' && !event.defaultPrevented) {
          event.preventDefault()
          ask.closePanel()
        }
      }}
      className={cn(
        'fixed inset-y-0 right-0 z-40 flex w-[min(26rem,100vw)] flex-col border-l bg-card',
        'xl:sticky xl:top-0 xl:right-auto xl:bottom-auto xl:z-auto xl:h-screen xl:w-auto',
        ask.picking && 'max-xl:hidden',
        // Dragging from the panel's own handle: the panel must stay in the page to keep the
        // pointer, so it only turns transparent to the eye and to the pointer.
        ask.dragging && 'max-xl:pointer-events-none max-xl:opacity-0',
      )}
    >
      <header className="border-b px-4 pt-3 pb-2">
        <div className="flex items-center gap-2">
          <h2 id={headingId} ref={heading} tabIndex={-1} className="mr-auto text-base font-semibold focus:outline-none">
            Ask about this matter
          </h2>
          <Button variant="ghost" size="icon-sm" onClick={ask.closePanel} aria-label="Close the Ask panel" title="Close">
            <X aria-hidden />
          </Button>
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
          <Link
            to={{ search: '?view=ask' }}
            // The panel goes with the view change, so focus moves to the page rather than being lost.
            onClick={() => requestAnimationFrame(() => document.getElementById('main')?.focus())}
            className="text-primary underline-offset-4 hover:underline"
          >
            Open in Ask view
          </Link>
          {ask.threadId !== null && closedThread === null && (
            <button type="button" onClick={startNewQuestion} className="text-primary underline-offset-4 hover:underline">
              New question
            </button>
          )}
        </div>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto px-4">
        {ask.threadId === null ? (
          <p className="py-4 text-sm text-muted-foreground">
            Point at a row, tile or step with the handle, or type a question. Each sentence of the answer comes with
            its sources.
          </p>
        ) : (
          <ChatThreadTurns matterId={matterId} threadId={ask.threadId} />
        )}
      </div>
      <div ref={footer} className="space-y-2 border-t px-4 py-3 empty:hidden">
        {closedThread !== null && (
          <ClosedThreadNote matterId={matterId} thread={closedThread} onNewQuestion={startNewQuestion} />
        )}
        {loaded && <ChatComposer matterId={matterId} withHandle />}
      </div>
    </aside>
  )
}
