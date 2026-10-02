import type { FactOf } from '@/api/types'
import { SourceChip } from '@/components/shared/SourceChip'
import { KIND_LABELS } from '@/lib/labels'

export function InjuryRow({ fact }: { fact: FactOf<'injury' | 'diagnosis'> }) {
  const { body_part: bodyPart, severity } = fact.value
  const details = [KIND_LABELS[fact.kind], bodyPart, severity].filter(Boolean)
  return (
    <li className="flex items-start justify-between gap-3 py-2">
      <div className="min-w-0">
        <p className="text-sm leading-snug">{fact.title}</p>
        <p className="mt-0.5 text-xs text-muted-foreground">{details.join(' · ')}</p>
      </div>
      <SourceChip fact={fact} className="mt-0.5" />
    </li>
  )
}
