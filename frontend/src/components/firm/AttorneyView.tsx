import type { MatterHeaderOut } from '@/api/types'
import { ActionBoard } from '@/components/firm/ActionBoard'
import { InjuriesList } from '@/components/firm/InjuriesList'
import { KpiStrip } from '@/components/firm/KpiStrip'
import { ProvidersSection } from '@/components/firm/ProvidersSection'
import { RankedFeed } from '@/components/firm/RankedFeed'

/** What the attorney works from: what is due, what matters, the medical side, and the money. */
export function AttorneyView({ matterId, header }: { matterId: number; header: MatterHeaderOut }) {
  return (
    <>
      <ActionBoard matterId={matterId} />
      <RankedFeed matterId={matterId} />
      <div className="grid grid-cols-[repeat(auto-fit,minmax(24rem,1fr))] items-start gap-6">
        <InjuriesList matterId={matterId} />
        <ProvidersSection matterId={matterId} />
      </div>
      <KpiStrip kpis={header.kpis} />
    </>
  )
}
