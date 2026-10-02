import type { StageOut } from '@/api/types'
import { RevealOnHover } from '@/components/firm/RevealOnHover'
import { SourceChipList } from '@/components/shared/SourceChipList'
import { STAGE_LABELS } from '@/lib/labels'

export function StagePill({ stage }: { stage: StageOut }) {
  if (stage.stage === null) {
    return (
      <span className="rounded-full bg-muted px-3 py-1 text-[13px] text-muted-foreground">Stage not found in file</span>
    )
  }
  return (
    <span
      className="group/src inline-flex items-center gap-2"
      title={stage.label ? `Recorded as "${stage.label}"` : undefined}
    >
      <span className="rounded-full bg-blue-100 px-3 py-1 text-[13px] font-semibold text-blue-700">
        {STAGE_LABELS[stage.stage]}
        {stage.inferred && <span className="ml-1.5 font-normal text-warning">inferred</span>}
      </span>
      <RevealOnHover>
        <SourceChipList facts={stage.facts} max={1} />
      </RevealOnHover>
    </span>
  )
}
