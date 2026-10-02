import type { FactRef } from '@/api/types'
import { SourceChip } from '@/components/shared/SourceChip'

type SourceChipListProps = {
  facts: FactRef[]
  /** Chips beyond this are counted, not drawn, so a sum over many facts stays compact. */
  max?: number
}

export function SourceChipList({ facts, max = 3 }: SourceChipListProps) {
  const shown = facts.slice(0, max)
  const hidden = facts.length - shown.length
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      {shown.map((fact) => (
        <SourceChip key={fact.id} fact={fact} />
      ))}
      {hidden > 0 && <span className="text-[11px] text-muted-foreground">+{hidden} more</span>}
    </span>
  )
}
