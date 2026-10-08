import type { FactRef } from '@/api/types'
import { SourceChipList } from '@/components/shared/SourceChipList'

/** Chips drawn per sentence before the rest fold into "+N more". */
const CHIPS_PER_SENTENCE = 2

/** A cited page of a scanned document: the source an attorney most wants to open. */
function isDocumentPage(fact: FactRef): boolean {
  return fact.source_type === 'document' && fact.page_no !== null
}

/**
 * How a brief sentence shows the facts it rests on. This is the one place that decides
 * the brief's citation design, so changing it (for example to a clickable section that
 * opens its documents) does not touch the sentences or their rows.
 *
 * Document pages come first, so a scanned page is among the visible chips whenever the
 * sentence cites one, rather than folded behind the Clio record, notes and tasks. The
 * rest keep the order the brief listed them in.
 */
export function BriefCitations({ facts, describedBy }: { facts: FactRef[]; describedBy?: string }) {
  const ordered = [...facts.filter(isDocumentPage), ...facts.filter((fact) => !isDocumentPage(fact))]
  return <SourceChipList facts={ordered} max={CHIPS_PER_SENTENCE} expandable describedBy={describedBy} />
}
