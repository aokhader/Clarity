import { useLayoutEffect, useRef, useState } from 'react'

import type { ProviderItemOut } from '@/api/types'
import { Button } from '@/components/ui/button'
import { formatDate, formatMoney } from '@/lib/format'
import { KIND_LABELS } from '@/lib/labels'
import { cn } from '@/lib/utils'

type ProviderItemListProps = {
  items: ProviderItemOut[]
  /** One plain sentence for when there is nothing to list. */
  empty: string
  /** Opens the cited page. Without it, items that have one show no "View page" button. */
  onOpenSource?: (item: ProviderItemOut) => void
  /** Show this many rows and scroll the rest; `label` names the scrolling region. */
  scroll?: { rows: number; label: string }
}

/**
 * The height of the first `rows` items, measured rather than assumed, because a long
 * label wraps onto a second line and makes its row taller.
 */
function useVisibleRowsHeight(rows: number | null) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [height, setHeight] = useState<number | null>(null)

  useLayoutEffect(() => {
    const container = containerRef.current
    if (rows === null || container === null) {
      setHeight(null)
      return
    }
    const measure = () => {
      const last = container.querySelector<HTMLElement>(`:scope > ul > li:nth-child(${rows})`)
      setHeight(last ? last.offsetTop + last.offsetHeight : null)
    }
    measure()
    // Wrapping changes with the width, so measure again whenever it changes.
    const observer = new ResizeObserver(measure)
    observer.observe(container)
    return () => observer.disconnect()
  }, [rows])

  return { containerRef, height }
}

export function ProviderItemList({ items, empty, onOpenSource, scroll }: ProviderItemListProps) {
  const scrolls = scroll !== undefined && items.length > scroll.rows
  const { containerRef, height } = useVisibleRowsHeight(scrolls ? scroll.rows : null)

  if (items.length === 0) {
    return <p className="text-sm text-muted-foreground">{empty}</p>
  }
  return (
    <>
      <div
        ref={containerRef}
        // A scrolling region has to take focus, or keyboard users cannot reach its rest.
        {...(scrolls && { role: 'region', 'aria-label': scroll.label, tabIndex: 0 })}
        className={scrolls ? 'relative overflow-y-auto rounded-md focus-visible:outline-2 focus-visible:outline-ring' : undefined}
        style={scrolls && height !== null ? { maxHeight: height } : undefined}
      >
        <ul className="divide-y">
          {items.map((item) => (
            <li key={item.fact_id} className="flex items-baseline gap-4 py-2 text-sm">
              <span className="w-24 shrink-0 tabular-nums text-muted-foreground">
                {item.on ? formatDate(item.on) : 'Undated'}
              </span>
              <span className="min-w-0 flex-1">
                {item.kind === 'lien' && (
                  <span className="mr-2 rounded-sm border px-1.5 py-px text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
                    {KIND_LABELS.lien}
                  </span>
                )}
                {item.label}
              </span>
              {item.amount_cents !== null && (
                <span
                  className={cn(
                    'shrink-0 tabular-nums',
                    // A lien's amount is set apart from the bills' column, which the total adds up.
                    item.kind === 'lien' ? 'text-muted-foreground' : 'font-medium',
                  )}
                >
                  {formatMoney(item.amount_cents)}
                </span>
              )}
              {onOpenSource && item.has_source && (
                <Button
                  variant="outline"
                  size="xs"
                  className="self-center"
                  onClick={() => onOpenSource(item)}
                  aria-label={`View the page for ${item.label}`}
                >
                  View page
                </Button>
              )}
            </li>
          ))}
        </ul>
      </div>
      {scrolls && (
        <p className="mt-1.5 text-xs text-muted-foreground">
          Showing {scroll.rows} of {items.length}. Scroll the list for the rest.
        </p>
      )}
    </>
  )
}
