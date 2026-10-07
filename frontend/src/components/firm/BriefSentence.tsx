import type { DraftMentionOut, FactRef } from '@/api/types'
import { BriefCitations } from '@/components/firm/BriefCitations'
import { BriefMarkedText } from '@/components/firm/BriefMarkedText'

/**
 * Where the text's last word starts: the point after which the last word and the
 * citations wrap as one unit. A checked figure is never cut, so if the last word is part
 * of one, the unit starts before that figure.
 */
function wrapPoint(text: string, start: number, end: number, mentions: DraftMentionOut[]): number {
  let point = text.lastIndexOf(' ', end - 1) + 1
  for (const mention of [...mentions].reverse()) {
    if (mention.start < point && point < mention.end) point = text.lastIndexOf(' ', mention.start - 1) + 1
  }
  return Math.max(point, start)
}

type BriefSentenceProps = {
  text: string
  /** The facts the sentence cites; its chips sit after its last word. */
  facts: FactRef[]
  mentions: DraftMentionOut[]
}

/**
 * One sentence of the brief, or its headline. Its last word and its citations wrap as a
 * unit, so a chip can never land at the start of a line where it would read as the next
 * sentence's source. Text with no citations marks its matching figures with their chips.
 */
export function BriefSentence({ text, facts, mentions }: BriefSentenceProps) {
  const start = text.length - text.trimStart().length
  const end = text.trimEnd().length
  const point = wrapPoint(text, start, end, mentions)
  const marks = { text, mentions, markSupported: facts.length === 0 }
  return (
    <span>
      <BriefMarkedText {...marks} from={start} to={point} />
      <span className="whitespace-nowrap">
        <BriefMarkedText {...marks} from={point} to={end} />
        {facts.length > 0 && (
          <>
            {' '}
            <BriefCitations facts={facts} />
          </>
        )}
      </span>{' '}
    </span>
  )
}
