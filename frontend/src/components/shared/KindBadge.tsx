import type { FactKind } from '@/api/types'
import { KIND_LABELS } from '@/lib/labels'

export function KindBadge({ kind }: { kind: FactKind }) {
  return (
    <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
      {KIND_LABELS[kind]}
    </span>
  )
}
