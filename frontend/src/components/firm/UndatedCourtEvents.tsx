import { Fragment, useId } from 'react'

import { useMatterUndatedCourtEvents } from '@/api/matters'
import type { FactOut } from '@/api/types'
import { BriefCitations } from '@/components/firm/BriefCitations'
import { LITIGATION_EVENT_LABELS } from '@/lib/labels'

function eventWord(fact: FactOut): string {
  return fact.kind === 'litigation_event' ? LITIGATION_EVENT_LABELS[fact.value.event] : 'Court event'
}

/**
 * The court events the file states without a date, as one quiet line under the story so
 * far: each by its type word with its chips. Nothing is drawn while loading, on an error
 * (the story reports its own), or when every court event is dated.
 */
export function UndatedCourtEvents({ matterId }: { matterId: number }) {
  const events = useMatterUndatedCourtEvents(matterId)
  const baseId = useId()
  if (!events.isSuccess || events.data.length === 0) return null
  return (
    <p className="mt-2 text-sm text-muted-foreground">
      Also in the file, without a date:{' '}
      {events.data.map((fact, index) => (
        <Fragment key={fact.id}>
          {index > 0 && <span aria-hidden> · </span>}
          <span className="inline-flex items-center gap-1.5">
            <span id={`${baseId}-${index}`} className="text-foreground">
              {eventWord(fact)}
            </span>
            <BriefCitations facts={[fact, ...fact.restated_by]} describedBy={`${baseId}-${index}`} />
          </span>
        </Fragment>
      ))}
    </p>
  )
}
