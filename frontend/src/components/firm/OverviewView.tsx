import type { MatterHeaderOut } from '@/api/types'
import { BottomLine } from '@/components/firm/BottomLine'
import { CaseMetadata } from '@/components/firm/CaseMetadata'
import { ChangesSince } from '@/components/firm/ChangesSince'
import { WhereItStands } from '@/components/firm/WhereItStands'

/** The case at a glance, under the matter's identity: what changed, key facts, and the brief. */
export function OverviewView({ matterId, header }: { matterId: number; header: MatterHeaderOut }) {
  return (
    <>
      <ChangesSince matterId={matterId} />
      <CaseMetadata matterId={matterId} header={header} />
      <BottomLine matterId={matterId} />
      <WhereItStands matterId={matterId} />
    </>
  )
}
