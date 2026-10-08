import type { KpiOut } from '@/api/types'
import { KpiTile } from '@/components/firm/KpiTile'
import { Panel } from '@/components/shared/Panel'

export function KpiStrip({ kpis }: { kpis: KpiOut[] }) {
  return (
    <Panel title="Financial overview">
      {kpis.length === 0 ? (
        <p className="text-sm text-muted-foreground">No figures found in the file.</p>
      ) : (
        <div className="-mx-5 grid grid-cols-4 divide-x">
          {kpis.map((kpi) => (
            <KpiTile key={kpi.name} kpi={kpi} />
          ))}
        </div>
      )}
    </Panel>
  )
}
