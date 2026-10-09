import { GripVertical } from 'lucide-react'
import { useEffect, useEffectEvent, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

import { askItemOfElement } from '@/lib/askItems'
import { useAskContext } from '@/lib/askState'
import { cn } from '@/lib/utils'

const TARGET = '[data-ask-item]'
const PICK_PROMPT = 'Pick an item to ask about. Escape to cancel.'

/** The target an event happened in, if any. */
function targetOf(node: EventTarget | null): HTMLElement | null {
  return node instanceof Element ? node.closest<HTMLElement>(TARGET) : null
}

type AskHandleProps = {
  /** Called once an item is attached, so the composer can take focus. */
  onPicked: () => void
}

/**
 * The grip that points at an item to ask about it (D49). Clicking it, or pressing Enter
 * on it, starts pick mode: every row, tile and step that can be asked about is outlined
 * and reachable with Tab, and the next one clicked or chosen with Enter is attached
 * (WCAG 2.5.7: a single pointer or the keyboard does what dragging does). Escape, or a
 * click anywhere else, cancels; focus then comes back here.
 */
export function AskHandle({ onPicked }: AskHandleProps) {
  const ask = useAskContext()
  const button = useRef<HTMLButtonElement>(null)
  // Only the handle that started pick mode listens for the pick.
  const [owner, setOwner] = useState(false)
  const picking = ask.picking && owner

  const start = () => {
    setOwner(true)
    ask.startPicking()
    ask.announce(PICK_PROMPT)
  }

  const stop = (picked: boolean) => {
    setOwner(false)
    ask.stopPicking()
    if (picked) onPicked()
    else requestAnimationFrame(() => button.current?.focus())
  }

  /** Attach the target an event happened in; false when it was not in one. */
  const pick = useEffectEvent((node: EventTarget | null): boolean => {
    const target = targetOf(node)
    const item = target && askItemOfElement(target)
    if (!item) return false
    ask.addItem(item)
    ask.announce(`Attached ${item.label}.`)
    stop(true)
    return true
  })

  const cancel = useEffectEvent(() => {
    ask.announce('Pointing cancelled.')
    stop(false)
  })

  // While picking, clicks and Enter or Space anywhere on the page are caught before the
  // row's own chips and links see them, so choosing a row does not also open its source.
  useEffect(() => {
    if (!picking) return
    const onClick = (event: MouseEvent) => {
      // The handle's own click ends pick mode through its handler.
      if (button.current?.contains(event.target as Node)) return
      event.preventDefault()
      event.stopPropagation()
      if (!pick(event.target)) cancel()
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        event.stopPropagation()
        cancel()
      } else if (event.key === 'Enter' && targetOf(event.target)) {
        event.preventDefault()
        event.stopPropagation()
        pick(event.target)
      } else if (event.key === ' ' && targetOf(event.target)) {
        // Space acts on key up, as a button does; stop the page scrolling meanwhile.
        event.preventDefault()
        event.stopPropagation()
      }
    }
    const onKeyUp = (event: KeyboardEvent) => {
      if (event.key === ' ' && targetOf(event.target)) {
        event.preventDefault()
        event.stopPropagation()
        pick(event.target)
      }
    }
    document.addEventListener('click', onClick, true)
    document.addEventListener('keydown', onKeyDown, true)
    document.addEventListener('keyup', onKeyUp, true)
    return () => {
      document.removeEventListener('click', onClick, true)
      document.removeEventListener('keydown', onKeyDown, true)
      document.removeEventListener('keyup', onKeyUp, true)
    }
  }, [picking])

  // A handle that goes away mid-pick (a change of view) must not leave the page in pick mode.
  const leave = useEffectEvent(() => {
    if (owner) ask.stopPicking()
  })
  useEffect(() => () => leave(), [])

  return (
    <>
      <button
        ref={button}
        type="button"
        aria-pressed={picking}
        aria-label="Point at an item to ask about it"
        title="Point at an item to ask about it"
        onClick={() => (picking ? stop(false) : start())}
        className={cn(
          'inline-flex size-9 shrink-0 cursor-grab touch-none items-center justify-center rounded-md border border-input bg-card text-muted-foreground hover:text-foreground',
          picking && 'border-primary text-primary',
        )}
      >
        <GripVertical aria-hidden className="size-4" />
      </button>
      {picking &&
        createPortal(
          // Seen, not announced: the status region already said it.
          <div className="fixed inset-x-4 bottom-4 z-40 flex flex-wrap items-center justify-center gap-x-3 gap-y-1 rounded-md border border-input bg-card px-3 py-2 text-sm sm:inset-x-auto sm:left-1/2 sm:-translate-x-1/2">
            <span>{PICK_PROMPT}</span>
            <button type="button" className="font-medium text-primary underline-offset-4 hover:underline">
              Cancel
            </button>
          </div>,
          document.body,
        )}
    </>
  )
}
