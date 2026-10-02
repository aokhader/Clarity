import { useSearchParams } from 'react-router'

/**
 * The source drawer's state lives in the URL as `?fact=ID`, so any view of a source
 * can be linked and the back button closes the drawer.
 */
export function useSourceDrawer() {
  const [params, setParams] = useSearchParams()
  const raw = params.get('fact')
  const factId = raw !== null && /^\d+$/.test(raw) ? Number(raw) : null

  const open = (id: number) =>
    setParams((current) => {
      const next = new URLSearchParams(current)
      next.set('fact', String(id))
      return next
    })

  const close = () =>
    setParams((current) => {
      const next = new URLSearchParams(current)
      next.delete('fact')
      return next
    })

  return { factId, open, close }
}
