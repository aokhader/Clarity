import type { KpiOut } from '@/api/types'
import { KpiTile } from '@/components/firm/KpiTile'

export function KpiStrip({ kpis }: { kpis: KpiOut[] }) {
  return (
    <section aria-label="Key figures" className="grid grid-cols-4 divide-x rounded-lg border bg-card">
      {kpis.map((kpi) => (
        <KpiTile key={kpi.name} kpi={kpi} />
      ))}
    </section>
  )
}
