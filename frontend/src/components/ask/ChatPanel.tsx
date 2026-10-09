import { X } from 'lucide-react'
import { useEffect, useId, useRef } from 'react'
import { Link } from 'react-router'

import { ChatComposer } from '@/components/ask/ChatComposer'
import { ChatThreadTurns } from '@/components/ask/ChatThreadTurns'
import { Button } from '@/components/ui/button'
import { ASK_PANEL_ATTRIBUTE, useAskContext } from '@/lib/askState'
import { cn } from '@/lib/utils'

/**
 * The thread beside the page (D49). It is not a dialog: the page stays usable, and a
 * chip in it opens the source drawer, which hands focus back to the chip. From xl up it
 * is the page's third column, sticky and full height; narrower, it lies over the right
 * of the page, under the drawer, and steps aside while an item is being picked so the
 * rows can be seen. Escape closes it and returns focus to what opened it.
 */
export function ChatPanel({ matterId }: { matterId: number }) {
  const ask = useAskContext()
  const headingId = useId()
  const heading = useRef<HTMLHeadingElement>(null)
  const { panelWantsFocus, panelFocused } = ask

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
          {ask.threadId !== null && (
            <button type="button" onClick={ask.newQuestion} className="text-primary underline-offset-4 hover:underline">
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
      <div className="border-t px-4 py-3">
        <ChatComposer matterId={matterId} withHandle />
      </div>
    </aside>
  )
}
