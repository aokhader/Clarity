import { GripVertical } from 'lucide-react'
import { useEffect, useEffectEvent, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { createPortal } from 'react-dom'

import { askItemOfElement } from '@/lib/askItems'
import { useAskContext } from '@/lib/askState'
import { cn } from '@/lib/utils'

const TARGET = '[data-ask-item]'
const HOVER_ATTRIBUTE = 'data-ask-hover'
const PICK_PROMPT = 'Pick an item to ask about. Escape to cancel.'
/** A press that moves less than this is a click, which starts pick mode instead. */
const DRAG_THRESHOLD_PX = 4
/** The ghost chip sits this far below and right of the pointer, so the target stays in view. */
const GHOST_OFFSET_PX = 12

/** The target an event happened in, if any. */
function targetOf(node: EventTarget | null): HTMLElement | null {
  return node instanceof Element ? node.closest<HTMLElement>(TARGET) : null
}

/** A drag in progress: where it started and last was, whether it has moved enough to count, and the target under it. */
type Drag = {
  pointerId: number
  startX: number
  startY: number
  x: number
  y: number
  moved: boolean
  hover: HTMLElement | null
}

type AskHandleProps = {
  /** Called once an item is attached, so the composer can take focus. */
  onPicked: () => void
}

/**
 * The grip that points at an item to ask about it (D49), in two ways.
 *
 * Drag it onto a row, tile or step and let go: that item is attached. Pointer events
 * only, so mouse, pen and touch all work; a drop anywhere else, Escape, or a cancelled
 * pointer attaches nothing.
 *
 * Or click it, or press Enter on it, to start pick mode: every target is outlined and
 * reachable with Tab, and the next one clicked or chosen with Enter is attached. This is
 * the single-pointer and keyboard path WCAG 2.5.7 asks for. Escape, or a click anywhere
 * else, cancels, and focus comes back here.
 */
export function AskHandle({ onPicked }: AskHandleProps) {
  const ask = useAskContext()
  const button = useRef<HTMLButtonElement>(null)
  const ghost = useRef<HTMLDivElement>(null)
  const drag = useRef<Drag | null>(null)
  // Only the handle that started pick mode listens for the pick.
  const [owner, setOwner] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [overTarget, setOverTarget] = useState(false)
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

  /** Mark the target under the pointer, and only it, for the outline. */
  const hover = (target: HTMLElement | null) => {
    const current = drag.current
    if (current === null || current.hover === target) return
    current.hover?.removeAttribute(HOVER_ATTRIBUTE)
    target?.setAttribute(HOVER_ATTRIBUTE, '')
    current.hover = target
    setOverTarget(target !== null)
  }

  /** End a drag; with `attach`, the target under the pointer is attached. */
  const endDrag = (attach: boolean) => {
    const current = drag.current
    if (current === null) return
    const target = current.hover
    hover(null)
    drag.current = null
    if (button.current?.hasPointerCapture(current.pointerId)) button.current.releasePointerCapture(current.pointerId)
    if (!current.moved) return
    setDragging(false)
    ask.setDragging(false)
    // The click a drag ends with is not a click on whatever lies under the pointer.
    const swallow = (event: MouseEvent) => {
      event.preventDefault()
      event.stopPropagation()
    }
    document.addEventListener('click', swallow, { capture: true, once: true })
    setTimeout(() => document.removeEventListener('click', swallow, true), 0)
    const item = attach && target ? askItemOfElement(target) : null
    if (item) {
      ask.addItem(item)
      ask.announce(`Attached ${item.label}.`)
      onPicked()
    } else {
      ask.announce('Nothing attached.')
    }
  }
  const dropDrag = useEffectEvent(() => endDrag(false))

  // Escape drops the drag without attaching anything.
  useEffect(() => {
    if (!dragging) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      event.preventDefault()
      event.stopPropagation()
      dropDrag()
    }
    document.addEventListener('keydown', onKeyDown, true)
    return () => document.removeEventListener('keydown', onKeyDown, true)
  }, [dragging])

  /** Put the ghost chip by the pointer; it is moved directly, not re-rendered, on every move. */
  const placeGhost = () => {
    const current = drag.current
    if (ghost.current && current) {
      ghost.current.style.transform = `translate(${current.x + GHOST_OFFSET_PX}px, ${current.y + GHOST_OFFSET_PX}px)`
    }
  }

  const onPointerDown = (event: ReactPointerEvent<HTMLButtonElement>) => {
    // While picking, a press on the handle is only the click that ends pick mode.
    if (event.button !== 0 || picking) return
    event.currentTarget.setPointerCapture(event.pointerId)
    const { pointerId, clientX: x, clientY: y } = event
    drag.current = { pointerId, startX: x, startY: y, x, y, moved: false, hover: null }
  }

  const onPointerMove = (event: ReactPointerEvent<HTMLButtonElement>) => {
    const current = drag.current
    if (current === null || current.pointerId !== event.pointerId) return
    if (!current.moved) {
      if (Math.hypot(event.clientX - current.startX, event.clientY - current.startY) < DRAG_THRESHOLD_PX) return
      current.moved = true
      setDragging(true)
      ask.setDragging(true)
      ask.announce('Drop the handle on an item to ask about it. Escape to cancel.')
    }
    current.x = event.clientX
    current.y = event.clientY
    placeGhost()
    // The ghost ignores the pointer, so this finds what lies under it.
    hover(targetOf(document.elementFromPoint(event.clientX, event.clientY)))
  }

  const onPointerUp = (event: ReactPointerEvent<HTMLButtonElement>) => {
    if (drag.current?.pointerId === event.pointerId) endDrag(true)
  }

  // A handle that goes away mid-pick or mid-drag (a change of view) must not leave the page in that state.
  const leave = useEffectEvent(() => {
    if (owner) ask.stopPicking()
    if (drag.current?.moved) ask.setDragging(false)
    drag.current?.hover?.removeAttribute(HOVER_ATTRIBUTE)
  })
  useEffect(() => () => leave(), [])

  return (
    <>
      <button
        ref={button}
        type="button"
        aria-pressed={picking}
        aria-label="Point at an item to ask about it"
        title="Drag onto an item, or click and then pick one"
        onClick={() => (picking ? stop(false) : start())}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={() => endDrag(false)}
        onLostPointerCapture={() => endDrag(false)}
        className={cn(
          'inline-flex size-9 shrink-0 cursor-grab touch-none items-center justify-center rounded-md border border-input bg-card text-muted-foreground select-none hover:text-foreground',
          (picking || dragging) && 'border-primary text-primary',
        )}
      >
        <GripVertical aria-hidden className="size-4" />
      </button>
      {dragging &&
        createPortal(
          <div
            ref={(element) => {
              ghost.current = element
              placeGhost()
            }}
            aria-hidden
            className="pointer-events-none fixed top-0 left-0 z-50 inline-flex items-center gap-1 rounded-sm border border-primary bg-card px-1.5 py-0.5 text-xs font-medium text-primary"
          >
            <GripVertical className="size-3" />
            {overTarget ? 'Let go to attach' : 'Ask about…'}
          </div>,
          document.body,
        )}
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
