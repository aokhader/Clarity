import { Link } from 'react-router'

import { useMatterKeyEvents } from '@/api/matters'
import { KeyEventRow } from '@/components/firm/KeyEventRow'
import { LoadError } from '@/components/shared/LoadError'
import { Section } from '@/components/shared/Section'
import { Skeleton } from '@/components/ui/skeleton'

/**
 * What has happened so far, in order: about ten key events from the server, the incident
 * pinned first, numbered oldest first. The full timeline is one link away.
 */
export function KeyEvents({ matterId }: { matterId: number }) {
  const events = useMatterKeyEvents(matterId)
  return (
    <Section title="The story so far" aside="oldest first">
      {events.isPending && (
        <div className="space-y-2" aria-label="Loading the key events">
          <Skeleton className="h-6" />
          <Skeleton className="h-6" />
          <Skeleton className="h-6 w-2/3" />
        </div>
      )}
      {events.isError && (
        <LoadError what="the key events" error={events.error} onRetry={() => void events.refetch()} />
      )}
      {events.isSuccess &&
        (events.data.length === 0 ? (
          <p className="text-sm text-muted-foreground">No key events found in the file.</p>
        ) : (
          <ol className="@container">
            {events.data.map((fact, index) => (
              <KeyEventRow key={fact.id} fact={fact} number={index + 1} />
            ))}
          </ol>
        ))}
      <Link
        to={{ search: '?view=attorney&feed=timeline' }}
        className="mt-3 inline-block text-sm font-medium text-primary underline-offset-4 hover:underline"
      >
        Full timeline
      </Link>
    </Section>
  )
}
