import { useEffect, useRef, useState } from 'react'

import type { FactRef } from '@/api/types'
import { SourceChip } from '@/components/shared/SourceChip'
import { useSourceDrawer } from '@/lib/useSourceDrawer'

const MORE_BUTTON =
  'inline-flex h-5 items-center rounded-sm px-1 align-middle text-[11px] font-medium text-muted-foreground transition-colors hover:text-primary focus-visible:outline-2 focus-visible:outline-ring'

type SourceChipListProps = {
  facts: FactRef[]
  /** Chips beyond this are counted, not drawn, so a sum over many facts stays compact. */
  max?: number
  /** Make the "+N more" count a button that draws the remaining chips. */
  expandable?: boolean
  /**
   * Step through the sources in the drawer instead of drawing them here: "+N more" opens
   * the first source not drawn, and every chip opens with Previous and Next across the
   * whole list, in this order (D46). Takes the place of `expandable`.
   */
  browse?: boolean
  /** The id of the text these chips cite (SourceChip). */
  describedBy?: string
}

export function SourceChipList({ facts, max = 3, expandable = false, browse = false, describedBy }: SourceChipListProps) {
  const { open } = useSourceDrawer()
  const [expanded, setExpanded] = useState(false)
  const listRef = useRef<HTMLSpanElement>(null)
  const shown = expanded ? facts : facts.slice(0, max)
  const hidden = facts.length - shown.length
  const firstHidden = facts[shown.length]
  const among = browse ? facts.map((fact) => fact.id) : undefined

  // The "+N more" button goes away once pressed, so focus moves to the first chip it revealed.
  useEffect(() => {
    if (expanded) listRef.current?.querySelectorAll<HTMLButtonElement>('button')[max]?.focus()
  }, [expanded, max])

  let more = null
  if (hidden > 0 && firstHidden !== undefined && browse) {
    more = (
      <button
        type="button"
        onClick={() => open(firstHidden.id, among)}
        aria-label={`Open source ${shown.length + 1} of ${facts.length}`}
        aria-describedby={describedBy}
        title="Open the next source"
        className={MORE_BUTTON}
      >
        +{hidden} more
      </button>
    )
  } else if (hidden > 0 && expandable) {
    more = (
      <button
        type="button"
        onClick={() => setExpanded(true)}
        aria-label={`Show ${hidden} more ${hidden === 1 ? 'source' : 'sources'}`}
        aria-describedby={describedBy}
        className={MORE_BUTTON}
      >
        +{hidden} more
      </button>
    )
  } else if (hidden > 0) {
    more = <span className="text-[11px] text-muted-foreground">+{hidden} more</span>
  }

  return (
    <span ref={listRef} className="inline-flex flex-wrap items-center gap-1">
      {shown.map((fact) => (
        <SourceChip key={fact.id} fact={fact} describedBy={describedBy} among={among} />
      ))}
      {more}
    </span>
  )
}
