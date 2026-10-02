import { Link } from 'react-router'

import { useMatters } from '@/api/matters'
import { LoadError } from '@/components/shared/LoadError'
import { Panel } from '@/components/shared/Panel'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDateTime } from '@/lib/format'

export function MatterList() {
  const matters = useMatters()
  return (
    <Panel title="Matters">
      {matters.isPending && <Skeleton className="h-10" aria-label="Loading matters" />}
      {matters.isError && (
        <LoadError what="the matters" error={matters.error} onRetry={() => void matters.refetch()} />
      )}
      {matters.isSuccess && matters.data.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No matters yet. Run <code>python -m app.cli sync</code>, or <code>seed-dev</code> for the invented one.
        </p>
      )}
      {matters.isSuccess && matters.data.length > 0 && (
        <ul className="divide-y">
          {matters.data.map((matter) => (
            <li key={matter.matter_id}>
              <Link
                to={`/matters/${matter.matter_id}`}
                className="flex items-baseline justify-between gap-4 py-2 hover:text-primary"
              >
                <span className="font-medium">
                  {matter.client_name ?? matter.description ?? `Matter ${matter.matter_id}`}
                  {matter.display_number && (
                    <span className="ml-2 text-sm font-normal text-muted-foreground">{matter.display_number}</span>
                  )}
                </span>
                <span className="text-xs text-muted-foreground">Synced {formatDateTime(matter.synced_at)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}
