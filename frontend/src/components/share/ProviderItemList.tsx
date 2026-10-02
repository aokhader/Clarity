import type { ProviderItemOut } from '@/api/types'
import { Button } from '@/components/ui/button'
import { formatDate, formatMoney } from '@/lib/format'

type ProviderItemListProps = {
  items: ProviderItemOut[]
  /** One plain sentence for when there is nothing to list. */
  empty: string
  /** Opens the cited page. Absent in the firm's preview, where no link is live. */
  onOpenSource?: (item: ProviderItemOut) => void
}

export function ProviderItemList({ items, empty, onOpenSource }: ProviderItemListProps) {
  if (items.length === 0) {
    return <p className="text-sm text-muted-foreground">{empty}</p>
  }
  return (
    <ul className="divide-y">
      {items.map((item) => (
        <li key={item.fact_id} className="flex items-baseline gap-4 py-2 text-sm">
          <span className="w-24 shrink-0 tabular-nums text-muted-foreground">
            {item.on ? formatDate(item.on) : 'Undated'}
          </span>
          <span className="min-w-0 flex-1">{item.label}</span>
          {item.amount_cents !== null && (
            <span className="shrink-0 tabular-nums font-medium">{formatMoney(item.amount_cents)}</span>
          )}
          {onOpenSource && item.has_source && (
            <Button
              variant="outline"
              size="xs"
              className="self-center"
              onClick={() => onOpenSource(item)}
              aria-label={`View the page for ${item.label}`}
            >
              View page
            </Button>
          )}
        </li>
      ))}
    </ul>
  )
}
