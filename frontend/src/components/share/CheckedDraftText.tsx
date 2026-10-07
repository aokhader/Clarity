import type { ReactNode } from 'react'

import type { CheckedDraft } from '@/api/shares'
import { DraftSentence } from '@/components/share/DraftSentence'

type CheckedDraftTextProps = {
  checked: CheckedDraft
  /** Replaces [start, end) of the checked text. Absent while the check is catching up. */
  onEdit?: (start: number, end: number, replacement: string) => void
}

/** The draft as it was checked, with each amount and date marked where it stands. */
export function CheckedDraftText({ checked, onEdit }: CheckedDraftTextProps) {
  const { text, check } = checked
  const parts: ReactNode[] = []
  let cursor = 0
  for (const sentence of check.sentences) {
    parts.push(text.slice(cursor, sentence.start))
    parts.push(<DraftSentence key={sentence.start} text={text} sentence={sentence} onEdit={onEdit} />)
    cursor = sentence.end
  }
  parts.push(text.slice(cursor))
  return <div className="text-sm leading-7 break-words whitespace-pre-wrap">{parts}</div>
}
