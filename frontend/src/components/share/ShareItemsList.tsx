import { Eye, EyeOff } from 'lucide-react'

import type { ShareItemOut } from '@/api/types'
import { SETTING_LABELS } from '@/components/share/shareSettings'
import { Button } from '@/components/ui/button'
import { factsRef } from '@/lib/askItems'
import { formatDate } from '@/lib/format'
import { useAskTargetProps } from '@/lib/useAskTarget'
import { cn } from '@/lib/utils'

type ShareItemsListProps = {
  items: ShareItemOut[]
  onToggle: (factId: number, hide: boolean) => void
}

/** Every fact the enabled sections release, each with a control to hold it back. */
export function ShareItemsList({ items, onToggle }: ShareItemsListProps) {
  const askTarget = useAskTargetProps()
  return (
    <section aria-labelledby="share-items-heading">
      <h3 id="share-items-heading" className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Included items ({items.filter((item) => !item.hidden).length} of {items.length})
      </h3>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">The sections turned on release no items.</p>
      ) : (
        <ul className="divide-y rounded-md border">
          {items.map((item) => (
            <li key={item.fact_id} {...askTarget(factsRef([{ id: item.fact_id }]), 'fact')} className="flex items-center gap-2 px-2 py-1.5 text-sm">
              <div className={cn('min-w-0 flex-1', item.hidden && 'text-muted-foreground line-through')}>
                <p className="truncate">{item.title}</p>
                <p className="text-xs text-muted-foreground no-underline">
                  {SETTING_LABELS[item.setting]}
                  {item.event_date && <span className="tabular-nums"> · {formatDate(item.event_date)}</span>}
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={() => onToggle(item.fact_id, !item.hidden)}
                aria-label={item.hidden ? `Include ${item.title}` : `Hide ${item.title}`}
                aria-pressed={item.hidden}
                title={item.hidden ? 'Include' : 'Hide from this provider'}
              >
                {item.hidden ? <EyeOff aria-hidden /> : <Eye aria-hidden />}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
