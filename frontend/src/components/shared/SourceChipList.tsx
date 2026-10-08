import { useEffect, useRef, useState } from 'react'

import type { FactRef } from '@/api/types'
import { SourceChip } from '@/components/shared/SourceChip'

type SourceChipListProps = {
  facts: FactRef[]
  /** Chips beyond this are counted, not drawn, so a sum over many facts stays compact. */
  max?: number
  /** Make the "+N more" count a button that draws the remaining chips. */
  expandable?: boolean
  /** The id of the text these chips cite (SourceChip). */
  describedBy?: string
}

export function SourceChipList({ facts, max = 3, expandable = false, describedBy }: SourceChipListProps) {
  const [expanded, setExpanded] = useState(false)
  const listRef = useRef<HTMLSpanElement>(null)
  const shown = expanded ? facts : facts.slice(0, max)
  const hidden = facts.length - shown.length

  // The "+N more" button goes away once pressed, so focus moves to the first chip it revealed.
  useEffect(() => {
    if (expanded) listRef.current?.querySelectorAll<HTMLButtonElement>('button')[max]?.focus()
  }, [expanded, max])

  return (
    <span ref={listRef} className="inline-flex flex-wrap items-center gap-1">
      {shown.map((fact) => (
        <SourceChip key={fact.id} fact={fact} describedBy={describedBy} />
      ))}
      {hidden > 0 &&
        (expandable ? (
          <button
            type="button"
            onClick={() => setExpanded(true)}
            aria-label={`Show ${hidden} more ${hidden === 1 ? 'source' : 'sources'}`}
            aria-describedby={describedBy}
            className="inline-flex h-5 items-center rounded-sm px-1 align-middle text-[11px] font-medium text-muted-foreground transition-colors hover:text-primary focus-visible:outline-2 focus-visible:outline-ring"
          >
            +{hidden} more
          </button>
        ) : (
          <span className="text-[11px] text-muted-foreground">+{hidden} more</span>
        ))}
    </span>
  )
}
