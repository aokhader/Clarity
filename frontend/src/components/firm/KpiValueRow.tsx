import type { KpiValueOut } from '@/api/types'
import { KpiFigure } from '@/components/firm/KpiFigure'
import { SourceChipList } from '@/components/shared/SourceChipList'
import { cn } from '@/lib/utils'

type KpiValueRowProps = {
  value: KpiValueOut
  /** Large for values that disagree and stand as equals; small for entries under a lead figure. */
  size: 'large' | 'small'
}

/** One of several values on a KPI tile: the figure, what it is, and its source. */
export function KpiValueRow({ value, size }: KpiValueRowProps) {
  return (
    // The figure's side never shrinks below its widest amount, so when the figure and the
    // chip do not both fit on a narrow tile, the chip moves under it instead of covering it.
    <li className="flex flex-wrap items-start gap-x-2">
      <div className="flex-1">
        {/* No nowrap here: KpiFigure keeps each amount whole, so a range can wrap after its dash. */}
        <p className={cn('font-semibold tabular-nums', size === 'large' ? 'text-xl' : 'text-base')}>
          <KpiFigure value={value} />
        </p>
        {value.label && <p className="text-xs text-muted-foreground">{value.label}</p>}
      </div>
      <div className="ml-auto">
        <SourceChipList facts={value.facts} max={1} />
      </div>
    </li>
  )
}
