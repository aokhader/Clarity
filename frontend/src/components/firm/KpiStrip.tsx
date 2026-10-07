import { DollarSign } from 'lucide-react'

import type { KpiOut } from '@/api/types'
import { KpiTile } from '@/components/firm/KpiTile'
import { Panel } from '@/components/shared/Panel'

export function KpiStrip({ kpis }: { kpis: KpiOut[] }) {
  return (
    <Panel title="Financial overview" icon={<DollarSign />}>
      {kpis.length === 0 ? (
        <p className="text-sm text-muted-foreground">No figures found in the file.</p>
      ) : (
        <div className="grid grid-cols-4 gap-4">
          {kpis.map((kpi) => (
            <KpiTile key={kpi.name} kpi={kpi} />
          ))}
        </div>
      )}
    </Panel>
  )
}
