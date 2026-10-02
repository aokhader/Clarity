import type { FactOut } from '@/api/types'
import { ActionItem } from '@/components/firm/ActionItem'
import { cn } from '@/lib/utils'

type ActionGroupProps = {
  title: string
  facts: FactOut[]
  /** One plain sentence for an empty group. */
  empty: string
  /** Overdue items are the only ones that earn a red count. */
  urgent?: boolean
}

export function ActionGroup({ title, facts, empty, urgent = false }: ActionGroupProps) {
  return (
    <div>
      <h3 className="flex items-center gap-2 text-sm font-semibold">
        {title}
        <span
          className={cn(
            'rounded-sm px-1.5 text-xs tabular-nums',
            urgent && facts.length > 0 ? 'bg-danger-soft text-danger' : 'bg-muted text-muted-foreground',
          )}
        >
          {facts.length}
        </span>
      </h3>
      {facts.length === 0 ? (
        <p className="mt-1 text-sm text-muted-foreground">{empty}</p>
      ) : (
        <ul className="divide-y">
          {facts.map((fact) => (
            <ActionItem key={fact.id} fact={fact} />
          ))}
        </ul>
      )}
    </div>
  )
}
