import type { FactRef } from '@/api/types'
import { SourceChip } from '@/components/shared/SourceChip'
import { useSourceDrawer } from '@/lib/useSourceDrawer'

type SourceChipListProps = {
  facts: FactRef[]
  /** Chips beyond this are counted, not drawn, so a sum over many facts stays compact. */
  max?: number
  /** The id of the text these chips cite (SourceChip). */
  describedBy?: string
}

/**
 * The sources of one item as chips. "+N more" opens the first source not drawn, and every
 * chip opens with the whole list, in this order, so the drawer steps through all of them
 * with Previous and Next (D46, D47).
 */
export function SourceChipList({ facts, max = 3, describedBy }: SourceChipListProps) {
  const { open } = useSourceDrawer()
  const shown = facts.slice(0, max)
  const firstHidden = facts[max]
  const among = facts.map((fact) => fact.id)

  return (
    // data-ask-skip: a row's chips are not part of its label when it is pointed at (D49).
    <span data-ask-skip className="inline-flex flex-wrap items-center gap-1">
      {shown.map((fact) => (
        <SourceChip key={fact.id} fact={fact} describedBy={describedBy} among={among} />
      ))}
      {firstHidden !== undefined && (
        <button
          type="button"
          onClick={() => open(firstHidden.id, among)}
          aria-label={`Open source ${max + 1} of ${facts.length}`}
          aria-describedby={describedBy}
          title="Open the next source"
          className="inline-flex h-5 items-center rounded-sm px-1 align-middle text-[11px] font-medium text-muted-foreground transition-colors hover:text-primary focus-visible:outline-2 focus-visible:outline-ring"
        >
          +{facts.length - max} more
        </button>
      )}
    </span>
  )
}
