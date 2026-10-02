import { useId, type ReactNode } from 'react'

import { cn } from '@/lib/utils'

type PanelProps = {
  title: string
  /** A lucide icon shown before the title. */
  icon?: ReactNode
  /** Shown beside the title, for example an item count. */
  aside?: ReactNode
  /** Controls on the right of the heading row. */
  actions?: ReactNode
  className?: string
  children: ReactNode
}

/** A titled section: a white card with an icon heading over a hairline rule. */
export function Panel({ title, icon, aside, actions, className, children }: PanelProps) {
  const headingId = useId()
  return (
    <section aria-labelledby={headingId} className={cn('rounded-2xl border bg-card shadow-xs', className)}>
      <header className="mx-6 flex items-center justify-between gap-3 border-b pt-5 pb-3.5">
        <div className="flex min-w-0 items-center gap-2.5">
          {icon !== undefined && (
            <span aria-hidden className="flex text-primary [&_svg]:size-[1.15rem]">
              {icon}
            </span>
          )}
          <h2 id={headingId} className="text-lg font-bold text-foreground">
            {title}
            {aside !== undefined && (
              <span className="ml-2 text-sm font-normal text-muted-foreground">{aside}</span>
            )}
          </h2>
        </div>
        {actions}
      </header>
      <div className="px-6 py-4">{children}</div>
    </section>
  )
}
