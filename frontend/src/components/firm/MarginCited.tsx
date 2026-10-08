import { useId, type ReactNode } from 'react'

import type { FactRef } from '@/api/types'
import { BriefCitations } from '@/components/firm/BriefCitations'
import { cn } from '@/lib/utils'

type MarginCitedProps = {
  /** The facts the text rests on, drawn in the gutter. None leaves the gutter empty. */
  facts: FactRef[]
  /** A row of a list, or `div` for a row that stands alone. */
  as?: 'li' | 'div'
  /** Type styles for the text. */
  className?: string
  children: ReactNode
}

/**
 * Text with its citations in a 14rem right-hand gutter, aligned to its first line, so the
 * text reads uninterrupted and still keeps its own chips (D3, D38). The parent sets
 * `@container`; below 40rem of width the chips drop under the text. Each chip is
 * described by the row's text, so two chips of one type tell apart by what they back.
 * Rows sit flush, so the margin rule runs unbroken down a list.
 */
export function MarginCited({ facts, as: Row = 'li', className, children }: MarginCitedProps) {
  const textId = useId()
  return (
    <Row
      className={cn(
        'relative grid grid-cols-1 items-baseline gap-x-4 gap-y-1 py-1.5',
        '@min-[40rem]:grid-cols-[minmax(0,1fr)_14rem]',
        '@min-[40rem]:before:absolute @min-[40rem]:before:inset-y-0 @min-[40rem]:before:right-[14rem] @min-[40rem]:before:w-px @min-[40rem]:before:bg-border',
      )}
    >
      <div id={textId} className={className}>
        {children}
      </div>
      <div className="min-w-0 @min-[40rem]:pl-4">
        {facts.length > 0 && <BriefCitations facts={facts} describedBy={textId} />}
      </div>
    </Row>
  )
}
