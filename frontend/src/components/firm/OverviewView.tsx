import type { MatterHeaderOut } from '@/api/types'
import { Brief } from '@/components/firm/Brief'
import { CaseMetadata } from '@/components/firm/CaseMetadata'
import { ChangesSince } from '@/components/firm/ChangesSince'
import { MatterHeader } from '@/components/firm/MatterHeader'

/** The case at a glance: client, what changed, key facts, the brief, and the stage. */
export function OverviewView({ matterId, header }: { matterId: number; header: MatterHeaderOut }) {
  return (
    <>
      <MatterHeader header={header} />
      <ChangesSince matterId={matterId} />
      <CaseMetadata matterId={matterId} header={header} />
      <Brief matterId={matterId} />
    </>
  )
}
