import { ChevronRight } from 'lucide-react'
import type { ReactNode } from 'react'

import type { FactRef } from '@/api/types'
import { useSourceDrawer } from '@/lib/useSourceDrawer'
import { cn } from '@/lib/utils'

type MetadataItemProps = {
  icon: ReactNode
  label: string
  /** The facts the value comes from. The card opens the first; with none it is not clickable. */
  facts?: FactRef[]
  /** Red for overdue, nothing otherwise. */
  urgent?: boolean
  /** The whole value as text, shown on hover when the card clamps it to two lines. */
  fullText?: string
  className?: string
  /** Phrasing content only, since the card is a button when it has a source. */
  children: ReactNode
}

/**
 * One case metadata card. Every card has the same shape: icon, label, and a value
 * clamped to two lines. A card backed by a fact opens that fact's source when clicked.
 */
export function MetadataItem({
  icon,
  label,
  facts = [],
  urgent = false,
  fullText,
  className,
  children,
}: MetadataItemProps) {
  const drawer = useSourceDrawer()
  const [source] = facts
  const lowConfidence = facts.some((fact) => fact.confidence === 'low')

  const content = (
    <>
      <span
        aria-hidden
        className={cn(
          'flex size-10 shrink-0 items-center justify-center rounded-lg [&_svg]:size-[1.05rem]',
          urgent ? 'bg-card text-danger' : 'bg-muted text-muted-foreground',
        )}
      >
        {icon}
      </span>
      <span className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="flex items-center gap-2 text-xs font-medium tracking-[0.08em] text-muted-foreground uppercase">
          {label}
          {/* The chip carried the low-confidence marker; the card keeps it. */}
          {lowConfidence && (
            <span className="rounded-sm border border-dashed border-warning px-1 text-[10px] tracking-normal text-warning normal-case">
              Low confidence
            </span>
          )}
        </span>
        <span className={cn('line-clamp-2 text-[15px] leading-snug', urgent && 'text-danger')}>{children}</span>
      </span>
      {source && (
        <ChevronRight
          aria-hidden
          className="size-4 shrink-0 self-center text-muted-foreground transition-colors group-hover:text-primary"
        />
      )}
    </>
  )

  const card = 'flex h-full w-full items-start gap-3 rounded-lg border p-4 text-left'
  if (!source) {
    return (
      <div title={fullText} className={cn(card, 'border-transparent bg-muted', className)}>
        {content}
      </div>
    )
  }
  return (
    <button
      type="button"
      title={fullText}
      onClick={() => drawer.open(source.id)}
      className={cn(
        card,
        'group cursor-pointer transition-colors focus-visible:outline-2 focus-visible:outline-ring',
        urgent
          ? 'border-danger/40 bg-danger-soft hover:border-danger'
          : 'bg-card hover:border-primary hover:bg-muted',
        className,
      )}
    >
      {content}
    </button>
  )
}
