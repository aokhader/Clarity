import { useMatterFeed } from '@/api/matters'
import { FeedRow } from '@/components/firm/FeedRow'
import { LoadError } from '@/components/shared/LoadError'
import { Loading } from '@/components/shared/Loading'
import { Skeleton } from '@/components/ui/skeleton'

/** The facts that matter most, ranked by significance. */
export function TopFacts({ matterId, limit }: { matterId: number; limit: number }) {
  const feed = useMatterFeed(matterId, limit)
  if (feed.isPending) {
    return (
      <Loading label="Loading the feed" className="space-y-2">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-6" />
        ))}
      </Loading>
    )
  }
  if (feed.isError) {
    return <LoadError what="the feed" error={feed.error} onRetry={() => void feed.refetch()} />
  }
  if (feed.data.length === 0) {
    return <p className="text-sm text-muted-foreground">No facts have been extracted for this matter yet.</p>
  }
  return (
    <ol className="divide-y">
      {feed.data.map((fact) => (
        <FeedRow key={fact.id} fact={fact} />
      ))}
    </ol>
  )
}
