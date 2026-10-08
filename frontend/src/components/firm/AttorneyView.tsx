import { ActionBoard } from '@/components/firm/ActionBoard'
import { InjuriesList } from '@/components/firm/InjuriesList'
import { ProvidersSection } from '@/components/firm/ProvidersSection'
import { RankedFeed } from '@/components/firm/RankedFeed'

/** What the attorney works from: what is due, what matters, and the medical side. */
export function AttorneyView({ matterId }: { matterId: number }) {
  return (
    <>
      <ActionBoard matterId={matterId} />
      <RankedFeed matterId={matterId} />
      <div className="grid grid-cols-[repeat(auto-fit,minmax(24rem,1fr))] items-start gap-6">
        <InjuriesList matterId={matterId} />
        <ProvidersSection matterId={matterId} />
      </div>
    </>
  )
}
