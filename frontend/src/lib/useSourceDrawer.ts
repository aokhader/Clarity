import { useSearchParams } from 'react-router'

import { useFrozenThread } from '@/lib/frozenThread'

/**
 * The element that opened the drawer, so closing it hands focus back (WCAG 2.4.3). A chip
 * inside the drawer replaces the drawer's content, not its opener, so it is not recorded.
 */
let opener: HTMLElement | null = null

/** Focus what opened the drawer, or the page's h1 when that is gone or the drawer was opened by a link. */
export function returnFocusFromDrawer() {
  const target = opener
  opener = null
  if (target?.isConnected) target.focus()
  else document.querySelector<HTMLElement>('main h1')?.focus()
}

/**
 * The most sources one item carries into the URL. A date the whole file states can cite
 * hundreds of records; a thousand ids keep the URL near 7KB, under the dev server's 16KB
 * header limit. Past this, the rest are left out and the drawer's count stops here.
 */
const MAX_SOURCES = 1000

/** `sources=3,9,12` as ids, in order and without repeats; anything malformed reads as no list. */
function parseSources(raw: string | null): number[] | null {
  if (raw === null || !/^\d+(,\d+)*$/.test(raw)) return null
  return [...new Set(raw.split(',').map(Number))].slice(0, MAX_SOURCES)
}

/** A whole-number id from the URL, or null. */
function parseId(raw: string | null): number | null {
  return raw !== null && /^\d+$/.test(raw) ? Number(raw) : null
}

/**
 * The source drawer's state lives in the URL as `?fact=ID`, so any view of a source
 * can be linked and the back button closes the drawer. A chip that cites one of several
 * sources for the same item also writes `&sources=ID,ID,...`, every source in the order
 * its row shows them, so the drawer can step through them (D46). A chip inside a closed
 * chat thread also writes `&frozen=THREAD_ID`, so the drawer opens the source as it was
 * cited when the thread closed (D54).
 */
export function useSourceDrawer() {
  const [params, setParams] = useSearchParams()
  const frozenThread = useFrozenThread()
  const factId = parseId(params.get('fact'))
  const listed = parseSources(params.get('sources'))
  // A list is only offered for the fact it was opened with, so a hand-edited URL cannot strand it.
  const sources = listed !== null && listed.length > 1 && factId !== null && listed.includes(factId) ? listed : null
  const frozenThreadId = factId !== null ? parseId(params.get('frozen')) : null

  /**
   * Opens a fact's source; with `among`, the drawer can step through those sources too.
   * Called from inside a closed thread, it opens the copy frozen with that thread.
   */
  const open = (id: number, among?: number[]) => {
    const active = document.activeElement
    if (active instanceof HTMLElement && active.closest('[role="dialog"]') === null) opener = active
    setParams((current) => {
      const next = new URLSearchParams(current)
      next.set('fact', String(id))
      if (among !== undefined && among.length > 1) next.set('sources', among.slice(0, MAX_SOURCES).join(','))
      else next.delete('sources')
      if (frozenThread !== null) next.set('frozen', String(frozenThread.threadId))
      else next.delete('frozen')
      return next
    })
  }

  /**
   * Moves to another source in the list, keeping `frozen`. It replaces the history entry,
   * so Back still closes the drawer.
   */
  const step = (id: number) =>
    setParams(
      (current) => {
        const next = new URLSearchParams(current)
        next.set('fact', String(id))
        return next
      },
      { replace: true },
    )

  const close = () =>
    setParams((current) => {
      const next = new URLSearchParams(current)
      next.delete('fact')
      next.delete('sources')
      next.delete('frozen')
      return next
    })

  return { factId, sources, frozenThreadId, open, step, close }
}
