import type { KpiOut } from '@/api/types'
import { KpiTile } from '@/components/firm/KpiTile'
import { Section } from '@/components/shared/Section'

/** The four money figures in one row, divided by hairlines; narrower, they stack in a grid. */
export function KpiStrip({ kpis }: { kpis: KpiOut[] }) {
  return (
    <Section title="Money">
      {kpis.length === 0 ? (
        <p className="text-sm text-muted-foreground">No figures found in the file.</p>
      ) : (
        <div className="@container">
          <div className="grid grid-cols-1 gap-x-8 gap-y-5 @min-[36rem]:grid-cols-2 @min-[60rem]:grid-cols-4 @min-[60rem]:divide-x">
            {kpis.map((kpi) => (
              <KpiTile key={kpi.name} kpi={kpi} />
            ))}
          </div>
        </div>
      )}
    </Section>
  )
}
