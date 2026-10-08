import type { MatterHeaderOut } from '@/api/types'
import { BottomLine } from '@/components/firm/BottomLine'
import { ChangesSince } from '@/components/firm/ChangesSince'
import { KpiStrip } from '@/components/firm/KpiStrip'
import { NowStrip } from '@/components/firm/NowStrip'
import { WhatHappened } from '@/components/firm/WhatHappened'
import { WhereItStands } from '@/components/firm/WhereItStands'

/**
 * The 90-second read, under the matter's identity: the bottom line, what happened, where
 * the case is now, the money, the brief, and what changed since the last visit. One ivory sheet
 * divided by hairlines, so no block is a card inside a card.
 */
export function OverviewView({ matterId, header }: { matterId: number; header: MatterHeaderOut }) {
  return (
    <div className="divide-y rounded-xl border bg-card px-8">
      <BottomLine matterId={matterId} />
      <WhatHappened matterId={matterId} account={header.incident_account} />
      <NowStrip matterId={matterId} header={header} />
      <KpiStrip kpis={header.kpis} />
      <WhereItStands matterId={matterId} />
      <ChangesSince matterId={matterId} />
    </div>
  )
}
