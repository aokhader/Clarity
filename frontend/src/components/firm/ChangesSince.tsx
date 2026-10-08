import { useEffect } from 'react'

import { useFirmUser } from '@/api/users'
import { useMatterChanges, useRecordVisit } from '@/api/visits'
import { FeedRow } from '@/components/firm/FeedRow'
import { LoadError } from '@/components/shared/LoadError'
import { Section } from '@/components/shared/Section'
import { formatDateTime } from '@/lib/format'

const MAX_SHOWN = 5

/**
 * What changed in the file since this user's last visit. The visit is recorded once
 * this visit's changes have loaded, and the list stays as loaded until the next visit.
 */
export function ChangesSince({ matterId }: { matterId: number }) {
  const user = useFirmUser()
  const userId = user?.id ?? null
  const changes = useMatterChanges(matterId, userId)
  const { mutate: recordVisit } = useRecordVisit(matterId)
  const loaded = changes.isSuccess

  useEffect(() => {
    if (loaded && userId !== null) recordVisit(userId)
  }, [loaded, userId, recordVisit])

  if (changes.isError) {
    return (
      <div className="py-5">
        <LoadError what="the changes" error={changes.error} onRetry={() => void changes.refetch()} />
      </div>
    )
  }
  if (!changes.isSuccess || user === null) return null

  const { last_opened_at: lastOpened, facts } = changes.data
  if (lastOpened === null) {
    return (
      <p className="py-5 text-sm text-muted-foreground">
        First time {user.name} has opened this matter, so everything on this page is new.
      </p>
    )
  }
  if (facts.length === 0) return null

  const hidden = facts.length - MAX_SHOWN
  return (
    <Section title="Since you last opened" aside={formatDateTime(lastOpened)}>
      <ol className="divide-y">
        {facts.slice(0, MAX_SHOWN).map((fact) => (
          <FeedRow key={fact.id} fact={fact} />
        ))}
      </ol>
      {hidden > 0 && <p className="mt-2 text-xs text-muted-foreground">And {hidden} more.</p>}
    </Section>
  )
}
