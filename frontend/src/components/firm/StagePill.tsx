import type { StageOut } from '@/api/types'
import { RevealOnHover } from '@/components/firm/RevealOnHover'
import { SourceChipList } from '@/components/shared/SourceChipList'
import { STAGE_LABELS } from '@/lib/labels'

export function StagePill({ stage }: { stage: StageOut }) {
  if (stage.stage === null) {
    return <span className="rounded-md border px-3 py-1.5 text-sm text-muted-foreground">Stage not found in file</span>
  }
  return (
    <span
      className="group/src inline-flex items-center gap-2 rounded-md border border-foreground/25 bg-card px-3 py-1.5 text-sm font-semibold"
      title={stage.label ? `Recorded as "${stage.label}"` : undefined}
    >
      {STAGE_LABELS[stage.stage]}
      {stage.inferred && <span className="text-xs font-normal text-warning">inferred</span>}
      <RevealOnHover>
        <SourceChipList facts={stage.facts} max={1} />
      </RevealOnHover>
    </span>
  )
}
