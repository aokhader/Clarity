import type { FeedView } from '@/lib/matterViews'
import { cn } from '@/lib/utils'

type FeedViewToggleProps = {
  view: FeedView
  topCount: number
  onChange: (view: FeedView) => void
}

/** Two depths: the facts that matter most, or every fact by date. */
export function FeedViewToggle({ view, topCount, onChange }: FeedViewToggleProps) {
  const options: [FeedView, string][] = [
    ['top', `Top ${topCount}`],
    ['timeline', 'Full timeline'],
  ]
  return (
    <div role="group" aria-label="Feed view" className="inline-flex rounded-md border p-0.5">
      {options.map(([value, label]) => (
        <button
          key={value}
          type="button"
          aria-pressed={view === value}
          onClick={() => onChange(value)}
          className={cn(
            'rounded-sm px-2 py-0.5 text-xs font-medium focus-visible:outline-2 focus-visible:outline-ring',
            view === value ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground',
          )}
        >
          {label}
        </button>
      ))}
    </div>
  )
}
