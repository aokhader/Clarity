import { RevealOnHover } from '@/components/firm/RevealOnHover'
import { SourceChipList } from '@/components/shared/SourceChipList'
import type { InjuryGroup } from '@/lib/facts'
import { KIND_LABELS } from '@/lib/labels'

/** One injury, with a chip for each page that states it. */
export function InjuryRow({ group }: { group: InjuryGroup }) {
  const { lead, facts } = group
  const { body_part: bodyPart, severity } = lead.value
  const details = [KIND_LABELS[lead.kind], bodyPart, severity].filter(Boolean)
  return (
    <li className="group/src flex items-start justify-between gap-3 rounded-lg bg-muted px-4 py-3">
      <div className="flex min-w-0 flex-col gap-0.5">
        <p className="text-[15px] font-medium">{lead.title}</p>
        <p className="text-[13px] text-muted-foreground">{details.join(' · ')}</p>
      </div>
      <RevealOnHover>
        <span className="flex max-w-56 justify-end">
          <SourceChipList facts={facts} max={2} expandable />
        </span>
      </RevealOnHover>
    </li>
  )
}
