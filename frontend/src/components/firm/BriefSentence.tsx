import type { BriefSentenceOut } from '@/api/types'
import { SourceChipList } from '@/components/shared/SourceChipList'

/**
 * One sentence of the brief. Its last word and its chips wrap as a unit, so a chip can
 * never land at the start of a line where it would read as the next sentence's source.
 */
export function BriefSentence({ sentence }: { sentence: BriefSentenceOut }) {
  const text = sentence.text.trim()
  const split = text.lastIndexOf(' ') + 1
  return (
    <span>
      {text.slice(0, split)}
      <span className="whitespace-nowrap">
        {text.slice(split)} <SourceChipList facts={sentence.facts} />
      </span>{' '}
    </span>
  )
}
