import { useSearchParams } from 'react-router'

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
 * The source drawer's state lives in the URL as `?fact=ID`, so any view of a source
 * can be linked and the back button closes the drawer.
 */
export function useSourceDrawer() {
  const [params, setParams] = useSearchParams()
  const raw = params.get('fact')
  const factId = raw !== null && /^\d+$/.test(raw) ? Number(raw) : null

  const open = (id: number) => {
    const active = document.activeElement
    if (active instanceof HTMLElement && active.closest('[role="dialog"]') === null) opener = active
    setParams((current) => {
      const next = new URLSearchParams(current)
      next.set('fact', String(id))
      return next
    })
  }

  const close = () =>
    setParams((current) => {
      const next = new URLSearchParams(current)
      next.delete('fact')
      return next
    })

  return { factId, open, close }
}
