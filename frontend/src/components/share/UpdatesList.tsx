import type { ProviderUpdateOut } from '@/api/types'
import { formatDate } from '@/lib/format'

export function UpdatesList({ updates }: { updates: ProviderUpdateOut[] }) {
  if (updates.length === 0) {
    return <p className="text-sm text-muted-foreground">No status changes yet.</p>
  }
  return (
    <ol className="divide-y">
      {updates.map((update, index) => (
        <li key={`${update.on}-${index}`} className="flex items-baseline gap-4 py-2 text-sm">
          <span className="w-24 shrink-0 tabular-nums text-muted-foreground">
            {update.on ? formatDate(update.on) : 'Undated'}
          </span>
          <span>{update.label}</span>
        </li>
      ))}
    </ol>
  )
}
