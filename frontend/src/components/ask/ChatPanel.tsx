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
      )}
    >
      <header className="flex flex-wrap items-center gap-x-2 gap-y-1 border-b px-4 py-3">
        <h2 id={headingId} ref={heading} tabIndex={-1} className="mr-auto text-base font-semibold focus:outline-none">
          Ask about this matter
        </h2>
        {ask.threadId !== null && (
          <Button variant="ghost" size="xs" onClick={ask.newQuestion}>
            New question
          </Button>
        )}
        <Button asChild variant="ghost" size="xs">
          <Link
            to={{ search: '?view=ask' }}
            onClick={() => requestAnimationFrame(() => document.querySelector<HTMLElement>('main h1')?.focus())}
          >
            Open in Ask view
          </Link>
        </Button>
        <Button variant="ghost" size="icon-sm" onClick={ask.closePanel} aria-label="Close the Ask panel" title="Close">
          <X aria-hidden />
        </Button>
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
        <ChatComposer matterId={matterId} />
      </div>
    </aside>
  )
}
