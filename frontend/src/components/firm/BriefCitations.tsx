import type { FactRef } from '@/api/types'
import { SourceChipList } from '@/components/shared/SourceChipList'

/** Chips drawn per sentence before the rest fold into "+N more". */
const CHIPS_PER_SENTENCE = 2

/**
 * How a brief sentence shows the facts it rests on. This is the one place that decides
 * the brief's citation design, so changing it (for example to a clickable section that
 * opens its documents) does not touch the sentences or the panel.
 */
export function BriefCitations({ facts }: { facts: FactRef[] }) {
  return <SourceChipList facts={facts} max={CHIPS_PER_SENTENCE} expandable />
}
