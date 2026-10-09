import type { MatterHeaderOut } from '@/api/types'
import { BottomLine } from '@/components/firm/BottomLine'
import { ChangesSince } from '@/components/firm/ChangesSince'
import { KeyEvents } from '@/components/firm/KeyEvents'
import { KpiStrip } from '@/components/firm/KpiStrip'
import { NowStrip } from '@/components/firm/NowStrip'
import { WhatHappened } from '@/components/firm/WhatHappened'
import { WhereItStands } from '@/components/firm/WhereItStands'

/**
 * The 90-second read, under the matter's identity: the bottom line, what happened, where
 * the case is now, the money, the story so far, what changed since the last visit, and the
 * brief. The story and the changes come before the brief because the first screen already
 * carries most of the brief's points; one scroll then shows what has happened, in order,
 * and what is new (the changes block is hidden when nothing is).
 *
 * Each block is its own ivory card on the paper, so one is told from the next at a glance
 * (D46). The cards are drawn here on the direct children, not by the blocks, so a block
 * that renders nothing leaves no empty card, and the earlier single sheet divided by
 * hairlines is this one line: `divide-y rounded-xl border bg-card px-4 sm:px-8`.
 */
export function OverviewView({ matterId, header }: { matterId: number; header: MatterHeaderOut }) {
  return (
    <div className="space-y-3 *:rounded-xl *:border *:bg-card *:px-4 sm:*:px-8">
      <BottomLine matterId={matterId} />
      <WhatHappened matterId={matterId} account={header.incident_account} />
      <NowStrip matterId={matterId} header={header} />
      <KpiStrip kpis={header.kpis} />
      <KeyEvents matterId={matterId} />
      <ChangesSince matterId={matterId} />
      <WhereItStands matterId={matterId} />
    </div>
  )
}
