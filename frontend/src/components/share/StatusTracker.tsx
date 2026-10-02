import { ChevronRight } from 'lucide-react'

import type { ProviderStatusOut } from '@/api/types'
import { Panel } from '@/components/shared/Panel'
import { formatDate } from '@/lib/format'
import { STAGE_LABELS } from '@/lib/labels'
import { cn } from '@/lib/utils'

/** The canonical stages in order, with the current one marked. Earlier stages are not
 * ticked off: a case can skip one, and a tick would claim it happened. */
export function StatusTracker({ status }: { status: ProviderStatusOut }) {
  return (
    <Panel title="Case status">
      <ol aria-label="Case stages" className="flex flex-wrap items-center gap-x-1 gap-y-2 text-sm">
        {status.stages.map((stage, index) => {
          const current = stage === status.current
          return (
            <li key={stage} className="flex items-center gap-1" aria-current={current ? 'step' : undefined}>
              {index > 0 && <ChevronRight aria-hidden className="size-3.5 text-muted-foreground/60" />}
              <span
                className={cn(
                  'rounded-md px-2 py-1',
                  current ? 'border border-foreground/30 bg-card font-semibold' : 'text-muted-foreground',
                )}
              >
                {STAGE_LABELS[stage]}
              </span>
            </li>
          )
        })}
      </ol>
      <p className="mt-3 text-sm">
        <span className="font-medium">{status.active ? 'Active' : 'Closed'}</span>
        {status.last_movement_on && (
          <span className="text-muted-foreground">
            {' '}
            · last movement on <span className="tabular-nums">{formatDate(status.last_movement_on)}</span>
          </span>
        )}
      </p>
      {status.current === null && (
        <p className="mt-1 text-sm text-muted-foreground">The file does not record a stage yet.</p>
      )}
    </Panel>
  )
}
