import { Link } from 'react-router'

import { useMatterKeyEvents } from '@/api/matters'
import { KeyEventRow } from '@/components/firm/KeyEventRow'
import { UndatedCourtEvents } from '@/components/firm/UndatedCourtEvents'
import { LoadError } from '@/components/shared/LoadError'
import { Loading } from '@/components/shared/Loading'
import { Section } from '@/components/shared/Section'
import { Skeleton } from '@/components/ui/skeleton'

/**
 * What has happened so far: about ten key events from the server, which picks them (the
 * incident pinned) and returns them oldest first. They are shown newest first, so the
 * latest turn of the case leads (D47), and numbered down, so each keeps its place in the
 * story and the incident stays 1. Then the court events the file gives no date for. The
 * full timeline is one link away.
 */
export function KeyEvents({ matterId }: { matterId: number }) {
  const events = useMatterKeyEvents(matterId)
  const newestFirst = events.isSuccess ? [...events.data].reverse() : []
  return (
    <Section title="The story so far" aside="newest first">
      {events.isPending && (
        <Loading label="Loading the key events" className="space-y-2">
          <Skeleton className="h-6" />
          <Skeleton className="h-6" />
          <Skeleton className="h-6 w-2/3" />
        </Loading>
      )}
      {events.isError && (
        <LoadError what="the key events" error={events.error} onRetry={() => void events.refetch()} />
      )}
      {events.isSuccess &&
        (events.data.length === 0 ? (
          <p className="text-sm text-muted-foreground">No key events found in the file.</p>
        ) : (
          <ol reversed className="@container">
            {newestFirst.map((fact, index) => (
              <KeyEventRow key={fact.id} fact={fact} number={newestFirst.length - index} />
            ))}
          </ol>
        ))}
      <UndatedCourtEvents matterId={matterId} />
      <Link
        to={{ search: '?view=attorney&feed=timeline' }}
        className="mt-3 inline-block text-sm font-medium text-primary underline-offset-4 hover:underline"
      >
        Full timeline
      </Link>
    </Section>
  )
}
