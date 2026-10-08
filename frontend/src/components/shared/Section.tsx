import { useId, type ReactNode } from 'react'

import { cn } from '@/lib/utils'

type SectionProps = {
  title: string
  /** Shown beside the title, for example the date a list starts from. */
  aside?: ReactNode
  className?: string
  children: ReactNode
}

/**
 * A titled block of a memo-style page: a small label heading and its content, with no
 * card of its own, so blocks can share one surface divided by hairlines.
 */
export function Section({ title, aside, className, children }: SectionProps) {
  const headingId = useId()
  return (
    <section aria-labelledby={headingId} className={cn('py-6', className)}>
      <h2 id={headingId} className="text-xs font-semibold tracking-[0.12em] text-muted-foreground uppercase">
        {title}
        {aside !== undefined && <span className="ml-2 font-normal tracking-normal normal-case">{aside}</span>}
      </h2>
      <div className="mt-3">{children}</div>
    </section>
  )
}
