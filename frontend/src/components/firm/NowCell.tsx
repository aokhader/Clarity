import { useId, type ReactNode } from 'react'

import type { FactRef } from '@/api/types'
import { SourceChipList } from '@/components/shared/SourceChipList'
import { factsRef } from '@/lib/askItems'
import type { StarterKind } from '@/lib/askStarters'
import { useAskTarget } from '@/lib/useAskTarget'

type NowCellProps = {
  label: string
  /** The facts the value comes from; their chips end the detail line. */
  facts?: FactRef[]
  /** The line under the value: when it falls due, a countdown, a date. */
  detail?: ReactNode
  /** The questions offered when the cell is pointed at (D49); a cell with no facts is no target. */
  askStarter?: StarterKind
  children: ReactNode
}

/**
 * One cell of Deadlines and follow-ups (NowStrip): a small label on its own line, the
 * value, then a detail line ending in the value's chips, so a label never wraps to make
 * room for them. In a row of four the cells are divided by hairlines; narrower, they stack.
 */
export function NowCell({ label, facts = [], detail, askStarter = 'deadline', children }: NowCellProps) {
  const valueId = useId()
  const askTarget = useAskTarget(factsRef(facts), askStarter)
  return (
    <div {...askTarget} className="min-w-0 @min-[60rem]:px-5 @min-[60rem]:first:pl-0 @min-[60rem]:last:pr-0">
      <h3 className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">{label}</h3>
      <div id={valueId} className="mt-1 text-[15px] leading-snug">
        {children}
      </div>
      {(detail || facts.length > 0) && (
        <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
          {detail}
          {facts.length > 0 && <SourceChipList facts={facts} max={1} describedBy={valueId} />}
        </p>
      )}
    </div>
  )
}
