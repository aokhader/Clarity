import { useState } from 'react'

import type { CallTargetOut } from '@/api/types'
import { ActiveCall } from '@/components/calls/ActiveCall'
import { CallNotes } from '@/components/calls/CallNotes'
import { CallTargetList } from '@/components/calls/CallTargetList'
import { RecentCalls } from '@/components/calls/RecentCalls'
import { TypedNumberForm } from '@/components/calls/TypedNumberForm'
import { Panel } from '@/components/shared/Panel'

/** The right pane shows a call being placed, a past call's notes, or how to begin. */
type Pane = { kind: 'call'; target: CallTargetOut } | { kind: 'notes'; callId: number } | null

/**
 * Calls (D8, option A): who to call next on the left, the chosen call on the right. The
 * call itself goes through this computer's phone app; Clarity transcribes this microphone
 * once everyone has agreed, and writes notes after the call. Nothing is written to Clio.
 */
export function CallsView({ matterId }: { matterId: number }) {
  const [pane, setPane] = useState<Pane>(null)
  const [onCall, setOnCall] = useState(false)
  // While a call is on, nothing else can take its place in the right pane.
  const choose = onCall ? null : (target: CallTargetOut) => setPane({ kind: 'call', target })
  return (
    <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]">
      <div className="flex flex-col gap-6">
        <CallTargetList
          matterId={matterId}
          chosenId={pane?.kind === 'call' ? pane.target.target_id : null}
          onChoose={choose}
        />
        <TypedNumberForm matterId={matterId} onAdded={choose} />
        <RecentCalls
          matterId={matterId}
          openCallId={pane?.kind === 'notes' ? pane.callId : null}
          onOpen={(callId) => !onCall && setPane({ kind: 'notes', callId })}
        />
      </div>
      {pane?.kind === 'call' && (
        <ActiveCall
          key={pane.target.target_id}
          matterId={matterId}
          target={pane.target}
          onActiveChange={setOnCall}
          onClose={() => setPane(null)}
        />
      )}
      {pane?.kind === 'notes' && (
        <Panel title="Call notes">
          <CallNotes key={pane.callId} callId={pane.callId} />
        </Panel>
      )}
      {pane === null && (
        <Panel title="Call">
          <p className="text-sm text-muted-foreground">
            Choose someone to call, or type a number. The call opens in this computer&apos;s phone app; with everyone&apos;s
            agreement, Clarity transcribes what this computer&apos;s microphone hears and writes notes afterwards.
          </p>
        </Panel>
      )}
    </div>
  )
}
