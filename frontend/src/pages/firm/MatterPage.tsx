import { useEffect } from 'react'
import { useParams } from 'react-router'

import type { MatterHeaderOut } from '@/api/types'
import { AskBar } from '@/components/ask/AskBar'
import { AskView } from '@/components/ask/AskView'
import { ChatPanel } from '@/components/ask/ChatPanel'
import { CallsView } from '@/components/calls/CallsView'
import { AttorneyView } from '@/components/firm/AttorneyView'
import { DocumentsView } from '@/components/firm/DocumentsView'
import { FirmSidebar } from '@/components/firm/FirmSidebar'
import { MatterFooter } from '@/components/firm/MatterFooter'
import { MatterShell } from '@/components/firm/MatterShell'
import { OverviewView } from '@/components/firm/OverviewView'
import { ProviderPreviewView } from '@/components/firm/ProviderPreviewView'
import { SourceDrawer } from '@/components/firm/SourceDrawer'
import { AskProvider } from '@/lib/askContext'
import { useAskContext } from '@/lib/askState'
import { MATTER_VIEWS, useMatterView, type MatterViewId } from '@/lib/matterViews'
import { cn } from '@/lib/utils'
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
    case 'ask':
      return <AskView matterId={matterId} />
  }
}

/** The rail, the view, and from xl up the Ask panel as a third column when it is open. */
function MatterLayout({ matterId, view }: { matterId: number; view: MatterViewId }) {
  const { panelOpen } = useAskContext()
  // The Ask view holds the thread itself, so the panel steps aside there.
  const panelShown = panelOpen && view !== 'ask'
  const viewLabel = MATTER_VIEWS.find((entry) => entry.id === view)?.label ?? ''

  return (
    <div
      className={cn(
        'grid min-h-screen grid-cols-1 lg:grid-cols-[15rem_minmax(0,1fr)]',
        panelShown && 'xl:grid-cols-[15rem_minmax(0,1fr)_26rem]',
      )}
    >
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
                {/* The Ask view has its own composer in the bar's place. */}
                {view !== 'ask' && <AskBar matterId={matterId} />}
                <ViewContent view={view} matterId={matterId} header={header} />
                <MatterFooter header={header} />
              </>
            )}
          </MatterShell>
        </div>
      </main>
      {panelShown && <ChatPanel matterId={matterId} />}
      <SourceDrawer />
    </div>
  )
}

export function MatterPage() {
  const matterId = Number(useParams().matterId)
  const view = useMatterView()
  // A new view starts at its top, not wherever the last one was scrolled to.
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [view])
  if (!Number.isInteger(matterId) || matterId <= 0) return <NotFoundPage />

  return (
    // Keyed by matter, so a question and its items never carry over to another matter.
    <AskProvider key={matterId}>
      <MatterLayout matterId={matterId} view={view} />
    </AskProvider>
  )
}
