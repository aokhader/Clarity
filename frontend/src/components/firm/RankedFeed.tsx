import { useMatterFeed } from '@/api/matters'
import { FeedRow } from '@/components/firm/FeedRow'
import { LoadError } from '@/components/shared/LoadError'
import { Panel } from '@/components/shared/Panel'
import { Skeleton } from '@/components/ui/skeleton'

const FEED_SIZE = 10

/** The facts that matter most, ranked by significance. */
export function RankedFeed({ matterId }: { matterId: number }) {
  const feed = useMatterFeed(matterId, FEED_SIZE)
  return (
    <Panel title="What matters" aside={`Top ${FEED_SIZE} by significance`}>
      {feed.isPending && (
        <div className="space-y-2" aria-label="Loading the feed">
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} className="h-6" />
          ))}
        </div>
      )}
      {feed.isError && <LoadError what="the feed" error={feed.error} onRetry={() => void feed.refetch()} />}
      {feed.isSuccess && feed.data.length === 0 && (
        <p className="text-sm text-muted-foreground">No facts have been extracted for this matter yet.</p>
      )}
      {feed.isSuccess && feed.data.length > 0 && (
        <ol className="divide-y">
          {feed.data.map((fact) => (
            <FeedRow key={fact.id} fact={fact} />
          ))}
        </ol>
      )}
    </Panel>
  )
}
