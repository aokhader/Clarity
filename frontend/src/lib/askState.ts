import { createContext, useContext } from 'react'

import type { AskItemRef } from '@/api/types'
import type { AskItem } from '@/lib/askItems'

/** Marks the side panel, so focus that starts inside it is not taken for its opener. */
export const ASK_PANEL_ATTRIBUTE = 'data-ask-panel'
/** Marks the Ask bar, where focus goes when what opened the panel is gone. */
export const ASK_BAR_ATTRIBUTE = 'data-ask-bar'

export type AskState = {
  /** The side panel holding the thread. */
  panelOpen: boolean
  /** The thread a question follows up; null starts a new one. */
  threadId: number | null
  /** The question being written, shared by the Ask bar and the composers. */
  draft: string
  /** What the user pointed at, at most MAX_ASK_ITEMS, each once. */
  items: AskItem[]
  /** Pick mode: the next item clicked or chosen with Enter is attached. */
  picking: boolean
  /** The handle is being dragged towards an item. */
  dragging: boolean
  /** The panel was just opened on request and should take focus; it says when it has. */
  panelWantsFocus: boolean
}

export type AskContextValue = AskState & {
  setDraft: (draft: string) => void
  setThreadId: (threadId: number | null) => void
  addItem: (item: AskItem) => void
  removeItem: (ref: AskItemRef) => void
  /** Empty the question and its items, after it has been asked. */
  clear: () => void
  /** Leave the thread as well: the next question starts a new one. */
  newQuestion: () => void
  openPanel: () => void
  closePanel: () => void
  /** The panel has taken the focus that opening it asked for. */
  panelFocused: () => void
  startPicking: () => void
  stopPicking: () => void
  setDragging: (dragging: boolean) => void
  /** Say something to screen readers through the page's one polite status region. */
  announce: (message: string) => void
}

/** What a target needs: whether pick mode is on, and the hint that describes it then. */
export type AskPickingValue = { picking: boolean; hintId: string }

export const AskContext = createContext<AskContextValue | null>(null)
// Kept apart from the rest, so every row that is a target does not re-render on each keystroke.
export const AskPickingContext = createContext<AskPickingValue | null>(null)

/** The page's point-and-ask state. Only components under AskProvider use it. */
export function useAskContext(): AskContextValue {
  const value = useContext(AskContext)
  if (value === null) throw new Error('useAskContext is used outside AskProvider')
  return value
}

/** Pick mode and its hint, or null outside AskProvider, where nothing is a target. */
export function useAskPicking(): AskPickingValue | null {
  return useContext(AskPickingContext)
}
