import { useParams } from 'react-router'

import { ActionBoard } from '@/components/firm/ActionBoard'
import { Brief } from '@/components/firm/Brief'
import { ChangesSince } from '@/components/firm/ChangesSince'
import { InjuriesList } from '@/components/firm/InjuriesList'
import { KpiStrip } from '@/components/firm/KpiStrip'
import { MatterShell } from '@/components/firm/MatterShell'
import { ProvidersSection } from '@/components/firm/ProvidersSection'
import { RankedFeed } from '@/components/firm/RankedFeed'
import { SourceDrawer } from '@/components/firm/SourceDrawer'
import { NotFoundPage } from '@/pages/NotFoundPage'

export function MatterPage() {
  const matterId = Number(useParams().matterId)
  if (!Number.isInteger(matterId) || matterId <= 0) return <NotFoundPage />

  return (
    <main className="mx-auto max-w-[1360px] px-8 py-6">
      <MatterShell matterId={matterId}>
        {(header) => (
          <>
            <KpiStrip kpis={header.kpis} />
            <div className="mt-6 grid grid-cols-[minmax(0,1fr)_26rem] items-start gap-6">
              <div className="space-y-6">
                <Brief matterId={matterId} />
                <ChangesSince matterId={matterId} />
                <RankedFeed matterId={matterId} />
              </div>
              <aside className="space-y-6">
                <ActionBoard matterId={matterId} />
                <InjuriesList matterId={matterId} />
                <ProvidersSection matterId={matterId} />
              </aside>
            </div>
          </>
        )}
      </MatterShell>
      <SourceDrawer />
    </main>
  )
}
