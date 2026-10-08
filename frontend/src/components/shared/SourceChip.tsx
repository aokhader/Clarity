import type { FactRef } from '@/api/types'
import { SOURCE_LABELS } from '@/lib/labels'
import { useSourceDrawer } from '@/lib/useSourceDrawer'
import { cn } from '@/lib/utils'

type SourceChipProps = {
  fact: FactRef
  /** The id of the text the chip cites, so two chips of one type are told apart by what they back. */
  describedBy?: string
  className?: string
}

/** Opens the fact's source in the drawer. A dashed outline marks low confidence. */
export function SourceChip({ fact, describedBy, className }: SourceChipProps) {
  const { open } = useSourceDrawer()
  const type = SOURCE_LABELS[fact.source_type]
  const label = fact.page_no !== null ? `${type} p.${fact.page_no}` : type
  const low = fact.confidence === 'low'
  return (
    <button
      type="button"
      onClick={() => open(fact.id)}
      aria-label={`Open source: ${label}${low ? ', low confidence' : ''}`}
      aria-describedby={describedBy}
      title={low ? 'Low confidence: check the source' : 'Open source'}
      className={cn(
        'inline-flex h-5 shrink-0 items-center rounded-sm border px-1.5 align-middle text-[11px] font-medium tabular-nums text-muted-foreground transition-colors hover:border-primary hover:text-primary focus-visible:outline-2 focus-visible:outline-ring',
        low && 'border-dashed border-warning text-warning',
        className,
      )}
    >
      {label}
    </button>
  )
}
