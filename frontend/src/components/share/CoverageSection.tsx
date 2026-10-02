import { CircleCheck, CircleDashed } from 'lucide-react'

import type { ProviderCoverageOut } from '@/api/types'
import { ProviderItemList } from '@/components/share/ProviderItemList'
import { Panel } from '@/components/shared/Panel'

export function CoverageSection({ coverage }: { coverage: ProviderCoverageOut }) {
  return (
    <Panel title="Coverage">
      {coverage.confirmed !== null &&
        (coverage.confirmed ? (
          <p className="flex items-center gap-2 text-sm font-medium">
            <CircleCheck aria-hidden className="size-4 text-success" />
            Insurance coverage confirmed
          </p>
        ) : (
          <p className="flex items-center gap-2 text-sm">
            <CircleDashed aria-hidden className="size-4 text-muted-foreground" />
            Not yet confirmed
          </p>
        ))}
      {coverage.limits !== null && (
        <div className={coverage.confirmed !== null ? 'mt-3' : undefined}>
          <ProviderItemList items={coverage.limits} empty="No policy limits on file." />
        </div>
      )}
    </Panel>
  )
}
