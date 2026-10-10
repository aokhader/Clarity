import { Lock } from 'lucide-react'

import type { NoteLockedOut } from '@/api/types'
import { MarkedText } from '@/components/shared/MarkedText'

type NoteRefusalProps = {
  /** The note exactly as it was sent; the locked spans are offsets into it. */
  note: string
  lock: NoteLockedOut
}

/**
 * The server's refusal of a share's note (D25), drawn like the composer's own lock: the
 * note with each figure the provider must not see marked in place, with a chip to the
 * internal fact behind it. It stands until the note is edited.
 */
export function NoteRefusal({ note, lock }: NoteRefusalProps) {
  const locked = [...lock.locked].sort((a, b) => a.start - b.start)
  return (
    <div role="alert" className="space-y-3">
      <p className="flex items-start gap-2 text-sm font-medium text-danger">
        <Lock aria-hidden className="mt-0.5 size-4 shrink-0" />
        Don&apos;t send: {lock.message.replace(/\.$/, '')}. Edit the marked figures to create the link.
      </p>
      <div className="rounded-sm bg-danger-soft px-2 py-1 text-sm leading-7 break-words whitespace-pre-wrap ring-1 ring-danger">
        <MarkedText text={note} mentions={locked} from={0} to={note.length} markSupported={false} />
      </div>
    </div>
  )
}
