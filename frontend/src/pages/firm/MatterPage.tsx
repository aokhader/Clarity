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
      return <AttorneyView matterId={matterId} />
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
  const viewLabel = MATTER_VIEWS.find((entry) => entry.id === view)?.label ?? ''

  return (
    <div className="grid min-h-screen grid-cols-1 lg:grid-cols-[15rem_minmax(0,1fr)]">
      {/* The first thing a keyboard reaches, so the rail can be skipped (WCAG 2.4.1). */}
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-card focus:px-3 focus:py-2 focus:text-sm focus:font-medium"
      >
        Skip to the matter
      </a>
      <FirmSidebar view={view} />
      <main id="main" tabIndex={-1} className="min-w-0 px-4 pt-6 pb-16 focus:outline-none sm:px-8 lg:px-16 lg:pt-8">
        <div className="mx-auto flex max-w-[1180px] flex-col gap-6">
          <MatterShell matterId={matterId} viewLabel={viewLabel}>
            {(header) => (
              <>
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
