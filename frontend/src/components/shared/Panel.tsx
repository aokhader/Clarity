import { useId, type ReactNode } from 'react'

import { cn } from '@/lib/utils'

type PanelProps = {
  title: string
  /** Shown beside the title, for example an item count. */
  aside?: ReactNode
  /** Controls on the right of the heading row. */
  actions?: ReactNode
  className?: string
  children: ReactNode
}

/** A titled section: an ivory surface with a hairline border, its heading over a hairline rule. */
export function Panel({ title, aside, actions, className, children }: PanelProps) {
  const headingId = useId()
  return (
    <section aria-labelledby={headingId} className={cn('rounded-xl border bg-card', className)}>
      <header className="mx-6 flex items-center justify-between gap-3 border-b pt-5 pb-3.5">
        <h2 id={headingId} className="min-w-0 text-lg font-semibold text-foreground">
          {title}
          {aside !== undefined && <span className="ml-2 text-sm font-normal text-muted-foreground">{aside}</span>}
        </h2>
        {actions}
      </header>
      <div className="px-6 py-4">{children}</div>
    </section>
  )
}
