import type { ReactNode } from 'react'

import type { DraftMentionOut } from '@/api/types'
import { DraftMentionMark } from '@/components/share/DraftMentionMark'

type BriefMarkedTextProps = {
  text: string
  /** The server's check of the text's amounts and dates; offsets are within `text`. */
  mentions: DraftMentionOut[]
  /** The stretch of `text` to draw, [from, to); a mention is drawn only if it lies inside. */
  from: number
  to: number
  /** Mark figures that match the file as well, with their chips, for text with no citations of its own. */
  markSupported: boolean
}

/**
 * Brief text with each figure that differs from today's file, or is not in it, marked in
 * place with what the file says (D12). Figures that match are left plain, since the
 * sentence's own chips already open their sources.
 */
export function BriefMarkedText({ text, mentions, from, to, markSupported }: BriefMarkedTextProps) {
  const parts: ReactNode[] = []
  let cursor = from
  for (const mention of mentions) {
    const inside = mention.start >= from && mention.end <= to
    if (!inside || (mention.verdict === 'supported' && !markSupported)) continue
    parts.push(text.slice(cursor, mention.start))
    parts.push(<DraftMentionMark key={mention.start} mention={mention} />)
    cursor = mention.end
  }
  parts.push(text.slice(cursor, to))
  return <>{parts}</>
}
