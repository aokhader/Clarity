import { Lock } from 'lucide-react'
import type { ReactNode } from 'react'

import type { DraftSentenceOut } from '@/api/types'
import { DraftMentionMark } from '@/components/share/DraftMentionMark'

type DraftSentenceProps = {
  /** The whole checked text; the sentence and its mentions are offsets into it. */
  text: string
  sentence: DraftSentenceOut
  /** Replaces [start, end) of the checked text. Absent while the check is catching up. */
  onEdit?: (start: number, end: number, replacement: string) => void
}

/**
 * One sentence of a checked draft. A sentence with no amount or date carries no mark. One
 * that mentions a fact the link keeps internal is locked with "Don't send".
 */
export function DraftSentence({ text, sentence, onEdit }: DraftSentenceProps) {
  if (sentence.verdict === 'unchecked') return <>{text.slice(sentence.start, sentence.end)}</>

  const parts: ReactNode[] = []
  let cursor = sentence.start
  for (const mention of sentence.mentions) {
    parts.push(text.slice(cursor, mention.start))
    parts.push(
      <DraftMentionMark
        key={mention.start}
        mention={mention}
        onUseFileValue={onEdit && ((value) => onEdit(mention.start, mention.end, value))}
      />,
    )
    cursor = mention.end
  }
  parts.push(text.slice(cursor, sentence.end))

  if (sentence.verdict !== 'do_not_send') return <span>{parts}</span>
  return (
    <span className="rounded-sm bg-danger-soft px-0.5 ring-1 ring-danger/40">
      <span className="mr-1 inline-flex items-center gap-1 align-middle text-xs font-semibold text-danger">
        <Lock aria-hidden className="size-3.5" />
        Don&apos;t send
      </span>
      {parts}
      {onEdit && (
        <button
          type="button"
          onClick={() => onEdit(sentence.start, sentence.end, '')}
          className="ml-1 rounded-sm border border-danger/50 px-1.5 align-middle text-xs font-medium text-danger hover:bg-card focus-visible:outline-2 focus-visible:outline-ring"
        >
          Remove sentence
        </button>
      )}
    </span>
  )
}
