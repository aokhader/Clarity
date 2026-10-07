import type { KpiValueOut } from '@/api/types'
import { KpiFigure } from '@/components/firm/KpiFigure'
import { RevealOnHover } from '@/components/firm/RevealOnHover'
import { SourceChipList } from '@/components/shared/SourceChipList'
import { cn } from '@/lib/utils'

type KpiValueRowProps = {
  value: KpiValueOut
  /** Large for values that disagree and stand as equals; small for entries under a lead figure. */
  size: 'large' | 'small'
  /** The tile's tint for the label line. */
  labelClass: string
}

/** One of several values on a KPI tile: the figure, what it is, and its source. */
export function KpiValueRow({ value, size, labelClass }: KpiValueRowProps) {
  return (
    <li className="flex items-start justify-between gap-2">
      <div className="min-w-0">
        <p className={cn('whitespace-nowrap font-semibold tabular-nums', size === 'large' ? 'text-xl' : 'text-base')}>
          <KpiFigure value={value} />
        </p>
        {value.label && <p className={cn('text-xs', labelClass)}>{value.label}</p>}
      </div>
      <RevealOnHover>
        <SourceChipList facts={value.facts} max={1} />
      </RevealOnHover>
    </li>
  )
}
