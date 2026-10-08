import { useId, type ReactNode } from 'react'

import { cn } from '@/lib/utils'

type PanelProps = {
  title: string
  /** h2 under a page's h1; h3 where the panel sits inside a section that has its own h2. */
  level?: 2 | 3
  /** Shown beside the title, for example an item count. */
  aside?: ReactNode
  /** Controls on the right of the heading row. */
  actions?: ReactNode
  className?: string
  children: ReactNode
}

/** A titled section: an ivory surface with a hairline border, its heading over a hairline rule. */
export function Panel({ title, level = 2, aside, actions, className, children }: PanelProps) {
  const headingId = useId()
  const Heading = level === 2 ? 'h2' : 'h3'
  return (
    <section aria-labelledby={headingId} className={cn('rounded-xl border bg-card', className)}>
      <header className="mx-6 flex items-center justify-between gap-3 border-b pt-5 pb-3.5">
        <Heading id={headingId} className="min-w-0 text-lg font-semibold text-foreground">
          {title}
          {aside !== undefined && <span className="ml-2 text-sm font-normal text-muted-foreground">{aside}</span>}
        </Heading>
        {actions}
      </header>
      <div className="px-6 py-4">{children}</div>
    </section>
  )
}
