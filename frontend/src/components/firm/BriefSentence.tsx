import type { DraftMentionOut } from '@/api/types'
import { MarkedText } from '@/components/shared/MarkedText'

type BriefSentenceProps = {
  text: string
  mentions: DraftMentionOut[]
  /**
   * Whether the text cites facts of its own, in its row's gutter. Text that cites none
   * marks its matching figures in place, each with its chip.
   */
  cited: boolean
}

/**
 * One sentence of the brief, or its headline, with each checked figure that differs from
 * today's file marked in place (D12). Its citations are drawn by its row (MarginCited).
 */
export function BriefSentence({ text, mentions, cited }: BriefSentenceProps) {
  const start = text.length - text.trimStart().length
  const end = text.trimEnd().length
  return <MarkedText text={text} mentions={mentions} from={start} to={end} markSupported={!cited} />
}
