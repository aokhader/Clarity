import type { MatterHeaderOut } from '@/api/types'
import { BottomLine } from '@/components/firm/BottomLine'
import { ChangesSince } from '@/components/firm/ChangesSince'
import { KpiStrip } from '@/components/firm/KpiStrip'
import { NowStrip } from '@/components/firm/NowStrip'
import { WhereItStands } from '@/components/firm/WhereItStands'

/** The case at a glance, under the matter's identity: what changed, the bottom line, now, the money, and the brief. */
export function OverviewView({ matterId, header }: { matterId: number; header: MatterHeaderOut }) {
  return (
    <>
      <ChangesSince matterId={matterId} />
      <BottomLine matterId={matterId} />
      <NowStrip matterId={matterId} header={header} />
      <KpiStrip kpis={header.kpis} />
      <WhereItStands matterId={matterId} />
    </>
  )
}
