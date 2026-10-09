import type { ChatTurnOut } from '@/api/types'
import { BriefSentence } from '@/components/firm/BriefSentence'
import { MarginCited } from '@/components/firm/MarginCited'
import { OpenQuestions } from '@/components/firm/OpenQuestions'
import { formatCount } from '@/lib/format'

/**
 * A finished answer, drawn as the brief is: each sentence a row with its chips in the
 * margin, and figures that differ from today's file marked in place (D12). Sentences the
 * file does not answer follow as a neutral list, with no chips, since they cite nothing.
 */
export function ChatAnswer({ turn }: { turn: ChatTurnOut }) {
  const cited = turn.sentences.filter((sentence) => !sentence.not_in_file)
  const unanswered = turn.sentences.filter((sentence) => sentence.not_in_file).map((sentence) => sentence.text)
  return (
    <>
      {cited.length > 0 && (
        <ul className="@container">
          {cited.map((sentence, index) => (
            <MarginCited key={index} facts={sentence.facts} className="text-[15px] leading-relaxed text-pretty">
              <BriefSentence text={sentence.text} mentions={sentence.mentions} cited={sentence.facts.length > 0} />
            </MarginCited>
          ))}
        </ul>
      )}
      {cited.length === 0 && unanswered.length === 0 && (
        <p className="text-sm text-muted-foreground">
          {turn.no_answer ? 'The file does not answer this.' : 'No sentence of the answer could be shown with a source.'}
        </p>
      )}
      <OpenQuestions questions={unanswered} />
      {turn.withdrawn > 0 && (
        <p className="mt-2 text-xs text-muted-foreground">
          {formatCount(turn.withdrawn, 'sentence')} withdrawn: a source changed since.
        </p>
      )}
    </>
  )
}
