import { useParams, useSearchParams } from 'react-router'

import { ActionBoard } from '@/components/firm/ActionBoard'
import { Brief } from '@/components/firm/Brief'
import { ChangesSince } from '@/components/firm/ChangesSince'
import { DocumentsView } from '@/components/firm/DocumentsView'
import { FirmSidebar } from '@/components/firm/FirmSidebar'
import { InjuriesList } from '@/components/firm/InjuriesList'
import { KpiStrip } from '@/components/firm/KpiStrip'
import { MatterFooter } from '@/components/firm/MatterFooter'
import { MatterShell } from '@/components/firm/MatterShell'
import { ProvidersSection } from '@/components/firm/ProvidersSection'
import { RankedFeed } from '@/components/firm/RankedFeed'
import { SourceDrawer } from '@/components/firm/SourceDrawer'
import { NotFoundPage } from '@/pages/NotFoundPage'

export function MatterPage() {
  const matterId = Number(useParams().matterId)
  const showDocuments = useSearchParams()[0].get('view') === 'documents'
  if (!Number.isInteger(matterId) || matterId <= 0) return <NotFoundPage />

  return (
    <div className="grid min-h-screen grid-cols-[16rem_minmax(0,1fr)]">
      <FirmSidebar showDocuments={showDocuments} />
      <main className="min-w-0 px-10 py-8">
        <div className="mx-auto max-w-[1280px]">
          <MatterShell matterId={matterId}>
            {(header) =>
              showDocuments ? (
                <DocumentsView matterId={matterId} />
              ) : (
              <>
                <div id="figures" className="scroll-mt-6">
                  <KpiStrip kpis={header.kpis} />
                </div>
                <div className="mt-6 grid grid-cols-[minmax(0,1fr)_26rem] items-start gap-6">
                  <div className="space-y-6">
                    <div id="brief" className="scroll-mt-6">
                      <Brief matterId={matterId} />
                    </div>
                    <ChangesSince matterId={matterId} />
                    <div id="feed" className="scroll-mt-6">
                      <RankedFeed matterId={matterId} />
                    </div>
                  </div>
                  <aside className="space-y-6">
                    <div id="actions" className="scroll-mt-6">
                      <ActionBoard matterId={matterId} />
                    </div>
                    <InjuriesList matterId={matterId} />
                    <div id="providers" className="scroll-mt-6">
                      <ProvidersSection matterId={matterId} />
                    </div>
                  </aside>
                </div>
                <MatterFooter header={header} />
              </>
              )
            }
          </MatterShell>
        </div>
      </main>
      <SourceDrawer />
    </div>
  )
}
