import { Mic, MicOff } from 'lucide-react'

import type { SpeechStatus, TranscriptSegment } from '@/lib/useSpeechTranscript'

const STATUS_TEXT: Record<SpeechStatus, string> = {
  idle: 'Not transcribing yet.',
  listening: 'Transcribing your microphone.',
  stopped: 'Transcription stopped.',
  paused: 'Transcription paused.',
  blocked: 'Transcription cannot run.',
}

type LiveTranscriptProps = {
  status: SpeechStatus
  segments: TranscriptSegment[]
  /** Words still being recognised, shown in grey until they settle. */
  interim: string
  problem: string | null
  /** Offered when transcription paused or was blocked while the call goes on. */
  onResume?: () => void
}

/** The transcript as it is written, with a plain statement of what is and is not heard. */
export function LiveTranscript({ status, segments, interim, problem, onResume }: LiveTranscriptProps) {
  const Icon = status === 'listening' ? Mic : MicOff
  return (
    <section aria-label="Live transcript" className="space-y-3">
      <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm">
        Only this computer&apos;s microphone is heard. The other person&apos;s side of the call is not transcribed.
      </p>
      <div role="status" aria-live="polite" className="flex items-center gap-2 text-sm font-medium">
        <Icon aria-hidden className={status === 'listening' ? 'size-4 text-danger' : 'size-4 text-muted-foreground'} />
        {STATUS_TEXT[status]}
      </div>
      {problem && (
        <div role="alert" className="flex items-center justify-between gap-3 rounded-md border border-danger/40 bg-danger-soft px-3 py-2 text-sm">
          <span>{problem}</span>
          {onResume && (status === 'paused' || status === 'blocked') && (
            <button
              type="button"
              onClick={onResume}
              className="shrink-0 rounded-sm border px-2 py-0.5 text-xs font-medium hover:bg-card focus-visible:outline-2 focus-visible:outline-ring"
            >
              Resume
            </button>
          )}
        </div>
      )}
      <div className="max-h-80 min-h-24 overflow-y-auto rounded-md border bg-card px-4 py-3 text-sm leading-relaxed">
        {segments.length === 0 && interim === '' ? (
          <p className="text-muted-foreground">What you say appears here.</p>
        ) : (
          <>
            {segments.map((segment) => (
              <p key={segment.id}>{segment.text}</p>
            ))}
            {interim && <p className="text-muted-foreground">{interim}</p>}
          </>
        )}
      </div>
    </section>
  )
}
