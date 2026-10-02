import type { FactOf } from '@/api/types'
import { RevealOnHover } from '@/components/firm/RevealOnHover'
import { SourceChip } from '@/components/shared/SourceChip'
import { KIND_LABELS } from '@/lib/labels'

export function InjuryRow({ fact }: { fact: FactOf<'injury' | 'diagnosis'> }) {
  const { body_part: bodyPart, severity } = fact.value
  const details = [KIND_LABELS[fact.kind], bodyPart, severity].filter(Boolean)
  return (
    <li className="group/src flex items-start justify-between gap-3 rounded-xl border border-slate-100 bg-slate-50/60 p-4">
      <div className="flex min-w-0 flex-col gap-0.5">
        <p className="text-[15px] font-medium">{fact.title}</p>
        <p className="text-[13px] text-muted-foreground">{details.join(' · ')}</p>
      </div>
      <RevealOnHover>
        <SourceChip fact={fact} />
      </RevealOnHover>
    </li>
  )
}
