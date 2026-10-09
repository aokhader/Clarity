import { X } from 'lucide-react'
import type { ReactNode } from 'react'

type AskItemChipProps = {
  /** What the item is, in a few words. */
  label: string
  /** Removes the item from the question being written; without it the chip is fixed. */
  onRemove?: () => void
  /** The item's source chips, on an asked question. */
  children?: ReactNode
}

/** An item pointed at, attached to a question: its label, its sources once asked, and a way to drop it before. */
export function AskItemChip({ label, onRemove, children }: AskItemChipProps) {
  return (
    <span className="inline-flex max-w-full flex-wrap items-center gap-x-1.5 gap-y-1 rounded-sm border border-input bg-card py-0.5 pr-0.5 pl-1.5 text-xs">
      <span className="min-w-0 [overflow-wrap:anywhere]">{label}</span>
      {children}
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          aria-label={`Remove ${label}`}
          title="Remove"
          className="inline-flex size-5 items-center justify-center rounded-sm text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <X aria-hidden className="size-3" />
        </button>
      )}
    </span>
  )
}
