import type { FactRef } from '@/api/types'
import { SourceChipList } from '@/components/shared/SourceChipList'

/** Chips drawn per sentence before the rest fold into "+N more". */
const CHIPS_PER_SENTENCE = 2
/**
 * Beyond this many sources "+N more" stays a count, as in DraftMentionMark: an account
 * that a hundred records restate would otherwise open into a wall of chips.
 */
const MAX_EXPANDED_CHIPS = 8

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
 * rest keep the order the brief listed them in. With `browse`, "+N more" opens the next
 * source in the drawer, which steps through all of them in this order (D46).
 */
export function BriefCitations({
  facts,
  describedBy,
  browse = false,
}: {
  facts: FactRef[]
  describedBy?: string
  browse?: boolean
}) {
  const ordered = [...facts.filter(isDocumentPage), ...facts.filter((fact) => !isDocumentPage(fact))]
  return (
    <SourceChipList
      facts={ordered}
      max={CHIPS_PER_SENTENCE}
      expandable={ordered.length <= MAX_EXPANDED_CHIPS}
      browse={browse}
      describedBy={describedBy}
    />
  )
}
