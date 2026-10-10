import { useSearchParams } from 'react-router'

/** The firm page's views, in sidebar order. The first is the default. */
export const MATTER_VIEWS = [
  { id: 'overview', label: 'Case Overview' },
  { id: 'attorney', label: 'For Attorney' },
  { id: 'provider', label: 'For Service Provider' },
  { id: 'documents', label: 'Documents' },
  { id: 'calls', label: 'Calls' },
  { id: 'ask', label: 'Ask' },
] as const

export type MatterViewId = (typeof MATTER_VIEWS)[number]['id']

function isMatterView(value: string | null): value is MatterViewId {
  return MATTER_VIEWS.some((view) => view.id === value)
}

/** What Matters on For Attorney: the top facts, or every fact by date. */
export type FeedView = 'top' | 'timeline'

/**
 * The feed named by `?feed=`, so the Overview can link straight to the full timeline.
 * Top is the default and leaves the URL without the parameter.
 */
export function useFeedView(): [FeedView, (view: FeedView) => void] {
  const [params, setParams] = useSearchParams()
  const view: FeedView = params.get('feed') === 'timeline' ? 'timeline' : 'top'
  const setView = (next: FeedView) =>
    setParams(
      (previous) => {
        const updated = new URLSearchParams(previous)
        if (next === 'timeline') updated.set('feed', 'timeline')
        else updated.delete('feed')
        return updated
      },
      { replace: true },
    )
  return [view, setView]
}

/** The view named by `?view=`, so each view can be linked and the back button works. */
export function useMatterView(): MatterViewId {
  const raw = useSearchParams()[0].get('view')
  return isMatterView(raw) ? raw : 'overview'
}
