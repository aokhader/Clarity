import { FeedViewToggle } from '@/components/firm/FeedViewToggle'
import { TimelineView } from '@/components/firm/TimelineView'
import { TopFacts } from '@/components/firm/TopFacts'
import { Panel } from '@/components/shared/Panel'
import { useFeedView } from '@/lib/matterViews'

const FEED_SIZE = 10

/** The ten facts that matter, with a toggle to every fact in the file. */
export function RankedFeed({ matterId }: { matterId: number }) {
  const [view, setView] = useFeedView()
  return (
    <Panel
      title="What matters"
      aside={view === 'top' ? `Top ${FEED_SIZE} by significance` : 'Every fact, newest first'}
      actions={<FeedViewToggle view={view} topCount={FEED_SIZE} onChange={setView} />}
    >
      {view === 'top' ? <TopFacts matterId={matterId} limit={FEED_SIZE} /> : <TimelineView matterId={matterId} />}
    </Panel>
  )
}
