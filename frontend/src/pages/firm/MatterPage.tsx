import { useEffect } from 'react'
import { useParams } from 'react-router'

import type { MatterHeaderOut } from '@/api/types'
import { CallsView } from '@/components/calls/CallsView'
import { AttorneyView } from '@/components/firm/AttorneyView'
import { DocumentsView } from '@/components/firm/DocumentsView'
import { FirmSidebar } from '@/components/firm/FirmSidebar'
import { MatterFooter } from '@/components/firm/MatterFooter'
import { MatterShell } from '@/components/firm/MatterShell'
import { OverviewView } from '@/components/firm/OverviewView'
import { ProviderPreviewView } from '@/components/firm/ProviderPreviewView'
import { SourceDrawer } from '@/components/firm/SourceDrawer'
import { MATTER_VIEWS, useMatterView, type MatterViewId } from '@/lib/matterViews'
import { NotFoundPage } from '@/pages/NotFoundPage'

function ViewContent({ view, matterId, header }: { view: MatterViewId; matterId: number; header: MatterHeaderOut }) {
  switch (view) {
    case 'overview':
      return <OverviewView matterId={matterId} header={header} />
    case 'attorney':
      return <AttorneyView matterId={matterId} header={header} />
    case 'provider':
      return <ProviderPreviewView matterId={matterId} />
    case 'documents':
      return <DocumentsView matterId={matterId} />
    case 'calls':
      return <CallsView matterId={matterId} />
  }
}

export function MatterPage() {
  const matterId = Number(useParams().matterId)
  const view = useMatterView()
  // A new view starts at its top, not wherever the last one was scrolled to.
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [view])
  if (!Number.isInteger(matterId) || matterId <= 0) return <NotFoundPage />
  const title = MATTER_VIEWS.find((entry) => entry.id === view)?.label

  return (
    <div className="grid min-h-screen grid-cols-[17rem_minmax(0,1fr)]">
      <FirmSidebar view={view} />
      <main className="min-w-0 px-16 pt-12 pb-16">
        <div className="mx-auto flex max-w-[1180px] flex-col gap-6">
          <MatterShell matterId={matterId}>
            {(header) => (
              <>
                <div className="mb-2 flex flex-col gap-1.5">
                  <p className="text-sm font-medium tracking-[0.06em] text-primary uppercase">
                    Matter {header.display_number ? `#${header.display_number}` : header.matter_id}
                  </p>
                  <h1 className="text-2xl font-bold tracking-tight text-slate-800">{title}</h1>
                </div>
                <ViewContent view={view} matterId={matterId} header={header} />
                <MatterFooter header={header} />
              </>
            )}
          </MatterShell>
        </div>
      </main>
      <SourceDrawer />
    </div>
  )
}
