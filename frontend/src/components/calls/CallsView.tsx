import { PhoneCall } from 'lucide-react'
import { useState } from 'react'

import type { CallTargetOut } from '@/api/calls'
import { ActiveCall } from '@/components/calls/ActiveCall'
import { CallTargetList } from '@/components/calls/CallTargetList'
import { TypedNumberForm } from '@/components/calls/TypedNumberForm'
import { Panel } from '@/components/shared/Panel'

/**
 * Calls (D8, option A): who to call next on the left, the chosen call on the right. The
 * call itself goes through this computer's phone app; Clarity transcribes this microphone
 * once everyone has agreed, and writes notes after the call. Nothing is written to Clio.
 */
export function CallsView({ matterId }: { matterId: number }) {
  const [chosen, setChosen] = useState<CallTargetOut | null>(null)
  const [onCall, setOnCall] = useState(false)
  const choose = onCall ? null : setChosen
  return (
    <div className="grid grid-cols-[minmax(0,26rem)_minmax(0,1fr)] items-start gap-6">
      <div className="flex flex-col gap-6">
        <CallTargetList matterId={matterId} chosenId={chosen?.target_id ?? null} onChoose={choose} />
        <TypedNumberForm matterId={matterId} onAdded={choose} />
      </div>
      {chosen ? (
        <ActiveCall
          key={chosen.target_id}
          matterId={matterId}
          target={chosen}
          onActiveChange={setOnCall}
          onClose={() => setChosen(null)}
        />
      ) : (
        <Panel title="Call" icon={<PhoneCall />}>
          <p className="text-sm text-muted-foreground">
            Choose someone to call, or type a number. The call opens in this computer&apos;s phone app; with everyone&apos;s
            agreement, Clarity transcribes your side and writes notes afterwards.
          </p>
        </Panel>
      )}
    </div>
  )
}
