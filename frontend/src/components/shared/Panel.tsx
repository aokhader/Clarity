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

/** A titled section: white surface, thin border, small-caps heading. */
export function Panel({ title, aside, actions, className, children }: PanelProps) {
  const headingId = useId()
  return (
    <section aria-labelledby={headingId} className={cn('rounded-lg border bg-card', className)}>
      <header className="flex items-center justify-between gap-3 border-b px-4 py-2.5">
        <h2 id={headingId} className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          {title}
          {aside !== undefined && <span className="ml-2 font-normal normal-case tracking-normal">{aside}</span>}
        </h2>
        {actions}
      </header>
      <div className="px-4 py-3">{children}</div>
    </section>
  )
}
