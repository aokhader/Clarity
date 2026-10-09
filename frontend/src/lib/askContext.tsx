import { useCallback, useEffect, useId, useMemo, useRef, useState, type ReactNode } from 'react'

import { MAX_ASK_ITEMS, askRefKey } from '@/lib/askItems'
import {
  ASK_PANEL_ATTRIBUTE,
  AskContext,
  AskPickingContext,
  type AskContextValue,
  type AskPickingValue,
  type AskState,
} from '@/lib/askState'

/** Focus what opened the panel, or the page's h1 when that is gone. */
function focusOpener(opener: HTMLElement | null) {
  if (opener?.isConnected) opener.focus()
  else document.querySelector<HTMLElement>('main h1')?.focus()
}

/**
 * The point-and-ask state of one matter page (D49): the panel, the thread, the question
 * being written, the items pointed at, and pick mode. It lives in React state, not the
 * URL, because the rail's links replace the query string and the panel and its question
 * must survive a change of view. Mounted by MatterPage only, so the provider page has
 * no targets, handle, bar or panel.
 */
export function AskProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AskState>({
    panelOpen: false,
    threadId: null,
    draft: '',
    items: [],
    picking: false,
    panelWantsFocus: false,
  })
  const [announcement, setAnnouncement] = useState('')
  const opener = useRef<HTMLElement | null>(null)
  const hintId = useId()

  const update = useCallback((patch: Partial<AskState>) => setState((current) => ({ ...current, ...patch })), [])

  const value = useMemo<AskContextValue>(() => {
    const openPanel = () => {
      const active = document.activeElement
      if (active instanceof HTMLElement && active.closest(`[${ASK_PANEL_ATTRIBUTE}]`) === null) opener.current = active
      update({ panelOpen: true, panelWantsFocus: true })
    }
    const closePanel = () => {
      update({ panelOpen: false })
      focusOpener(opener.current)
      opener.current = null
    }
    return {
      ...state,
      setDraft: (draft) => update({ draft }),
      setThreadId: (threadId) => update({ threadId }),
      addItem: (item) =>
        setState((current) => {
          const key = askRefKey(item.ref)
          if (current.items.some((existing) => askRefKey(existing.ref) === key)) return current
          // The newest item is kept; past the limit the oldest gives way.
          return { ...current, items: [...current.items, item].slice(-MAX_ASK_ITEMS) }
        }),
      removeItem: (ref) =>
        setState((current) => ({
          ...current,
          items: current.items.filter((item) => askRefKey(item.ref) !== askRefKey(ref)),
        })),
      clear: () => update({ draft: '', items: [] }),
      newQuestion: () => update({ draft: '', items: [], threadId: null }),
      openPanel,
      closePanel,
      panelFocused: () => update({ panelWantsFocus: false }),
      startPicking: () => update({ picking: true }),
      stopPicking: () => update({ picking: false }),
      announce: setAnnouncement,
    }
  }, [state, update])

  const picking = useMemo<AskPickingValue>(() => ({ picking: state.picking, hintId }), [state.picking, hintId])

  // Targets are outlined by index.css while this is set.
  useEffect(() => {
    document.documentElement.toggleAttribute('data-ask-picking', state.picking)
    return () => document.documentElement.removeAttribute('data-ask-picking')
  }, [state.picking])

  return (
    <AskContext.Provider value={value}>
      <AskPickingContext.Provider value={picking}>
        {children}
        <div role="status" className="sr-only">
          {announcement}
        </div>
        <span id={hintId} hidden>
          Press Enter to ask about this item.
        </span>
      </AskPickingContext.Provider>
    </AskContext.Provider>
  )
}
