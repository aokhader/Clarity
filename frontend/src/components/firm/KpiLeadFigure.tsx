import type { KpiValueOut } from '@/api/types'
import { KpiFigure } from '@/components/firm/KpiFigure'
import { useLargestFittingSize } from '@/lib/useLargestFittingSize'
import { cn } from '@/lib/utils'

/** Largest first. A range starts a size down, since it is twice as long as an amount. */
const AMOUNT_SIZES = ['text-kpi', 'text-2xl', 'text-xl', 'text-lg'] as const
const RANGE_SIZES = ['text-2xl', 'text-xl', 'text-lg'] as const

/**
 * A tile's lead figure, as large as fits. On a narrow tile a range takes a second line
 * after its dash, and a figure still too wide steps down a size: it is never cut off.
 */
export function KpiLeadFigure({ value }: { value: KpiValueOut }) {
  const single = value.amount_cents !== null
  const { ref, size } = useLargestFittingSize<HTMLParagraphElement>(
    single ? AMOUNT_SIZES : RANGE_SIZES,
    `${value.amount_cents} ${value.low_cents} ${value.high_cents}`,
  )
  return (
    <p
      ref={ref}
      className={cn(
        'mt-2 min-h-10 font-semibold tabular-nums',
        size,
        // The padding keeps one line of a range level with an amount's.
        single ? 'leading-10' : 'py-1 leading-8',
      )}
    >
      <KpiFigure value={value} />
    </p>
  )
}
