import { X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { saveTranscript, useEndCall, useStartCall } from '@/api/calls'
import { ApiError } from '@/api/client'
import type { CallTargetOut } from '@/api/types'
import { useFirmUser } from '@/api/users'
import { CallNotes } from '@/components/calls/CallNotes'
import { ConsentDialog } from '@/components/calls/ConsentDialog'
import { DialLink } from '@/components/calls/DialLink'
import { LiveTranscript } from '@/components/calls/LiveTranscript'
import { Panel } from '@/components/shared/Panel'
import { SourceChip } from '@/components/shared/SourceChip'
import { Button } from '@/components/ui/button'
import { CONSENT_TEXT } from '@/lib/callConsent'
import { useSpeechTranscript } from '@/lib/useSpeechTranscript'

/** The transcript is saved this often while the call is on, so a closed tab loses little. */
const SAVE_EVERY_MS = 5_000

/** Until the server side of Calls is in place, its routes answer 404. */
function serverMessage(error: Error, action: string): string {
  if (error instanceof ApiError && error.status === 404) {
    return `${action} once the server side of Calls is in place.`
  }
  return error.message
}

type ActiveCallProps = {
  matterId: number
  target: CallTargetOut
  /** Tells the view a call is on, so another one cannot be opened over it. */
  onActiveChange: (active: boolean) => void
  onClose: () => void
}

/**
 * One call: dial through the computer's phone app, ask for consent, transcribe this
 * microphone while the call is on, then end it and read the notes. Nothing is transcribed
 * until the server has logged the consent.
 */
export function ActiveCall({ matterId, target, onActiveChange, onClose }: ActiveCallProps) {
  const user = useFirmUser()
  const speech = useSpeechTranscript()
  const startCall = useStartCall(matterId)
  const endCall = useEndCall(matterId)
  const [asking, setAsking] = useState(false)
  const [declined, setDeclined] = useState(false)
  const [ending, setEnding] = useState(false)
  const [saveProblem, setSaveProblem] = useState<string | null>(null)
  const call = startCall.data ?? null
  const name = target.name ?? 'this person'
  const active = call !== null && !endCall.isSuccess

  useEffect(() => {
    onActiveChange(active)
    return () => onActiveChange(false)
  }, [active, onActiveChange])

  // The interval reads the latest transcript without restarting on every word.
  const transcriptRef = useRef(speech.transcript)
  useEffect(() => {
    transcriptRef.current = speech.transcript
  }, [speech.transcript])

  useEffect(() => {
    if (call === null || ending) return
    let saved = ''
    const timer = window.setInterval(() => {
      const text = transcriptRef.current
      if (text === saved) return
      saved = text
      saveTranscript(call.call_id, { text, final: false }).then(
        () => setSaveProblem(null),
        (error: Error) => setSaveProblem(`The transcript could not be saved: ${error.message}`),
      )
    }, SAVE_EVERY_MS)
    return () => window.clearInterval(timer)
  }, [call, ending])

  // Ending waits for the recogniser's last final results before the final save.
  const { mutate: finish } = endCall
  const endNotTried = endCall.isIdle
  useEffect(() => {
    if (!ending || call === null || speech.status === 'listening' || !endNotTried) return
    finish({ callId: call.call_id, transcript: speech.transcript })
  }, [ending, call, speech.status, speech.transcript, endNotTried, finish])

  function agreed() {
    setAsking(false)
    if (user === null) return
    startCall.mutate(
      { userId: user.id, body: { target_id: target.target_id, consent_confirmed: true, consent_text: CONSENT_TEXT } },
      { onSuccess: () => speech.start() },
    )
  }

  function end() {
    setEnding(true)
    speech.stop()
  }

  return (
    <Panel
      title={`Call ${name}`}
      actions={
        <Button variant="ghost" size="icon-sm" aria-label="Close this call" disabled={active} onClick={onClose}>
          <X />
        </Button>
      }
    >
      <div className="space-y-6">
        {target.reason && (
          <p className="text-sm">
            {target.reason} {target.reason_fact && <SourceChip fact={target.reason_fact} />}
          </p>
        )}

        <section aria-label="Place the call" className="space-y-2">
          <h3 className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">1. Place the call</h3>
          {target.phone ? (
            <DialLink phone={target.phone} />
          ) : (
            <p className="text-sm text-muted-foreground">No number on file. Type one under “Call a number not in Clio”.</p>
          )}
        </section>

        <section aria-label="Transcribe" className="space-y-3">
          <h3 className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">2. Transcribe</h3>
          {call === null && !speech.supported && (
            <p className="text-sm">Transcription needs Chrome. You can still place the call and take notes yourself.</p>
          )}
          {call === null && speech.supported && user === null && (
            <p className="text-sm text-muted-foreground">Choose a firm user to start transcribing.</p>
          )}
          {call === null && speech.supported && user !== null && (
            <div className="flex flex-wrap items-center gap-3">
              <Button size="sm" onClick={() => setAsking(true)} disabled={startCall.isPending}>
                {startCall.isPending ? 'Starting…' : declined ? 'Ask again' : 'Start transcribing'}
              </Button>
              {declined && <span className="text-sm text-muted-foreground">Declined: the call goes on without transcription.</span>}
            </div>
          )}
          {startCall.isError && (
            <p role="alert" className="text-sm text-danger">
              {serverMessage(startCall.error, 'Transcription can start')}
            </p>
          )}
          {call !== null && (
            <>
              <LiveTranscript
                status={speech.status}
                segments={speech.segments}
                interim={speech.interim}
                problem={speech.problem}
                onResume={ending ? undefined : speech.start}
              />
              {saveProblem && (
                <p role="alert" className="text-sm text-danger">
                  {saveProblem}
                </p>
              )}
              {!endCall.isSuccess && (
                <Button variant="destructive" size="sm" onClick={end} disabled={ending}>
                  {ending ? 'Ending…' : 'End call'}
                </Button>
              )}
            </>
          )}
        </section>

        {call !== null && (endCall.isSuccess || endCall.isError) && (
          <section aria-label="Notes" className="space-y-2">
            <h3 className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">3. Notes</h3>
            {endCall.isError ? (
              <p role="alert" className="flex items-center gap-3 text-sm text-danger">
                {serverMessage(endCall.error, 'Notes can be written')}
                <Button
                  variant="outline"
                  size="xs"
                  onClick={() => finish({ callId: call.call_id, transcript: speech.transcript })}
                >
                  Retry
                </Button>
              </p>
            ) : (
              <CallNotes callId={call.call_id} />
            )}
          </section>
        )}
      </div>
      {asking && (
        <ConsentDialog
          name={name}
          onAgreed={agreed}
          onDeclined={() => {
            setAsking(false)
            setDeclined(true)
          }}
          onClose={() => setAsking(false)}
        />
      )}
    </Panel>
  )
}
