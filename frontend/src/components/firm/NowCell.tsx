import { useId, type ReactNode } from 'react'

import type { FactRef } from '@/api/types'
import { SourceChipList } from '@/components/shared/SourceChipList'

type NowCellProps = {
  label: string
  /** The facts the value comes from; their chips sit beside the label. */
  facts?: FactRef[]
  children: ReactNode
}

/**
 * One cell of the Now strip: a small label, the value, and its chip. In a row of four the
 * cells are divided by hairlines (NowStrip); narrower, they stack in a grid.
 */
export function NowCell({ label, facts = [], children }: NowCellProps) {
  const valueId = useId()
  return (
    <div className="min-w-0 @min-[60rem]:px-5 @min-[60rem]:first:pl-0 @min-[60rem]:last:pr-0">
      <div className="flex min-h-5 items-start justify-between gap-2">
        <h3 className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">{label}</h3>
        {facts.length > 0 && <SourceChipList facts={facts} max={1} describedBy={valueId} />}
      </div>
      <div id={valueId} className="mt-1 text-[15px] leading-snug">
        {children}
      </div>
    </div>
  )
}
