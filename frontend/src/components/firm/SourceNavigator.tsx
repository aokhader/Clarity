import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useEffect } from 'react'
import { useParams } from 'react-router'

import { usePrefetchFrozenFactSources } from '@/api/chat'
import { usePrefetchFactSources } from '@/api/facts'
import { Button } from '@/components/ui/button'
import { useSourceDrawer } from '@/lib/useSourceDrawer'

/** At least a 40px target, like the drawer's close button. Disabled by aria, so focus stays put at either end. */
const STEP_BUTTON = 'h-10 px-3 aria-disabled:pointer-events-none aria-disabled:opacity-50'

/**
 * Previous and Next across every source of one item, at the top of the drawer, when a
 * chip or "+N more" opened it with the item's list (D46). The drawer keeps it mounted
 * while the next source loads, so focus stays on the button pressed, and the position is
 * announced as it changes. Its neighbours are fetched ahead, so a step shows at once.
 * The right padding keeps it clear of the drawer's close button. The buttons name what
 * they step through, since a scanned document's page viewer below has its own Previous
 * and Next.
 */
export function SourceNavigator() {
  const { factId, sources, frozenThreadId, step } = useSourceDrawer()
  const matterId = Number(useParams().matterId)
  const prefetchLive = usePrefetchFactSources()
  const prefetchFrozen = usePrefetchFrozenFactSources()
  const index = sources !== null && factId !== null ? sources.indexOf(factId) : -1
  const previous = index > 0 ? sources?.[index - 1] : undefined
  const next = index >= 0 ? sources?.[index + 1] : undefined

  useEffect(() => {
    const neighbours = [previous, next].filter((id) => id !== undefined)
    // A closed thread's chips step through its frozen copies (D54), so those are fetched ahead.
    if (frozenThreadId === null) prefetchLive(neighbours)
    else if (Number.isInteger(matterId)) prefetchFrozen(matterId, frozenThreadId, neighbours)
  }, [prefetchLive, prefetchFrozen, matterId, frozenThreadId, previous, next])

  if (sources === null || index < 0) return null
  return (
    // On a phone the buttons drop the visible "source" (their names keep it) and the count wraps under them.
    <nav
      aria-label="Sources for this item"
      className="flex min-h-16 flex-wrap items-center gap-x-2 gap-y-1 border-b px-6 py-3 pr-16"
    >
      <Button
        variant="outline"
        className={STEP_BUTTON}
        aria-disabled={previous === undefined}
        onClick={() => previous !== undefined && step(previous)}
      >
        <ChevronLeft aria-hidden />
        Previous<span className="max-sm:sr-only"> source</span>
      </Button>
      <Button
        variant="outline"
        className={STEP_BUTTON}
        aria-disabled={next === undefined}
        onClick={() => next !== undefined && step(next)}
      >
        Next<span className="max-sm:sr-only"> source</span>
        <ChevronRight aria-hidden />
      </Button>
      <p role="status" className="text-sm text-muted-foreground tabular-nums sm:ml-2">
        Source {index + 1} of {sources.length}
      </p>
    </nav>
  )
}
