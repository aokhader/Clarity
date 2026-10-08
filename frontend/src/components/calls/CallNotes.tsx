import { useCallDetail } from '@/api/calls'
import type { CallNoteKind, NotesStatus } from '@/api/types'
import { LoadError } from '@/components/shared/LoadError'
import { Loading } from '@/components/shared/Loading'
import { SourceChip } from '@/components/shared/SourceChip'
import { Skeleton } from '@/components/ui/skeleton'

const KIND_LABELS: Record<CallNoteKind, string> = {
  summary: 'Summary',
  commitment: 'Commitment',
  date: 'Date',
  amount: 'Amount',
  follow_up: 'Follow-up',
}

/** What to say when there are no notes to list; null when the notes are done. */
const STATUS_TEXT: Record<NotesStatus, string | null> = {
  not_started: 'Writing notes from the transcript…',
  running: 'Writing notes from the transcript…',
  no_model: 'No notes: the model settings are not configured, so only the transcript is kept.',
  failed: 'The notes could not be written. The transcript is kept.',
  done: null,
}

/** After the call: notes drawn from the transcript, each opening the words it came from. */
export function CallNotes({ callId }: { callId: number }) {
  const detail = useCallDetail(callId)
  if (detail.isPending) return <Loading label="Loading the call"><Skeleton className="h-32 w-full" /></Loading>
  if (detail.isError) {
    return <LoadError what="the call's notes" error={detail.error} onRetry={() => void detail.refetch()} />
  }

  const { call, transcript, notes } = detail.data
  const statusText = STATUS_TEXT[call.notes_status]
  return (
    <section aria-label="Notes from the call" className="space-y-3">
      <p className="text-sm text-muted-foreground">
        Transcribed from this computer&apos;s microphone, which on a speakerphone can include the other party.
      </p>
      {statusText && (
        <p role="status" className="text-sm">
          {statusText}
        </p>
      )}
      {call.notes_status === 'done' &&
        (notes.length === 0 ? (
          <p className="text-sm text-muted-foreground">No notes could be drawn from the transcript.</p>
        ) : (
          <ul className="divide-y rounded-md border">
            {notes.map((note) => (
              <li key={note.fact.id} className="flex items-start justify-between gap-3 px-3 py-2 text-sm">
                <span>
                  <span className="mr-2 text-xs font-semibold tracking-wider text-muted-foreground uppercase">
                    {KIND_LABELS[note.kind]}
                  </span>
                  {note.text}
                </span>
                <SourceChip fact={note.fact} />
              </li>
            ))}
          </ul>
        ))}
      <details className="rounded-md border px-3 py-2 text-sm">
        <summary className="cursor-pointer font-medium">Transcript</summary>
        <p className="mt-2 whitespace-pre-wrap text-muted-foreground">{transcript || 'Nothing was transcribed.'}</p>
      </details>
    </section>
  )
}
