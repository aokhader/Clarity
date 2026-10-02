import type { ReactNode } from 'react'

import type { FactRef } from '@/api/types'
import { RevealOnHover } from '@/components/firm/RevealOnHover'
import { SourceChipList } from '@/components/shared/SourceChipList'
import { cn } from '@/lib/utils'

type MetadataItemProps = {
  icon: ReactNode
  label: string
  /** The facts the value comes from; their chips show on hover. */
  facts?: FactRef[]
  /** Red for overdue, nothing otherwise. */
  urgent?: boolean
  children: ReactNode
}

/** One labelled value in the case metadata card. */
export function MetadataItem({ icon, label, facts = [], urgent = false, children }: MetadataItemProps) {
  return (
    <div className="group/src flex items-start gap-3">
      <span
        aria-hidden
        className={cn(
          'flex size-10 shrink-0 items-center justify-center rounded-lg border [&_svg]:size-[1.05rem]',
          urgent ? 'border-danger-soft bg-danger-soft text-danger' : 'border-slate-100 bg-slate-50 text-slate-600',
        )}
      >
        {icon}
      </span>
      <div className="flex min-w-0 flex-col gap-1.5 pt-px">
        <span className="text-xs font-medium tracking-[0.08em] text-muted-foreground uppercase">{label}</span>
        <div className={cn('flex flex-wrap items-center gap-1.5 text-[15px]', urgent && 'text-danger')}>
          {children}
          {facts.length > 0 && (
            <RevealOnHover>
              <SourceChipList facts={facts} max={2} />
            </RevealOnHover>
          )}
        </div>
      </div>
    </div>
  )
}
