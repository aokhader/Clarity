import { useSearchParams } from 'react-router'

/** The firm page's views, in sidebar order. The first is the default. */
export const MATTER_VIEWS = [
  { id: 'overview', label: 'Case Overview' },
  { id: 'attorney', label: 'For Attorney' },
  { id: 'provider', label: 'For Service Provider' },
  { id: 'documents', label: 'Documents' },
  { id: 'calls', label: 'Calls' },
] as const

export type MatterViewId = (typeof MATTER_VIEWS)[number]['id']

function isMatterView(value: string | null): value is MatterViewId {
  return MATTER_VIEWS.some((view) => view.id === value)
}

/** The view named by `?view=`, so each view can be linked and the back button works. */
export function useMatterView(): MatterViewId {
  const raw = useSearchParams()[0].get('view')
  return isMatterView(raw) ? raw : 'overview'
}
