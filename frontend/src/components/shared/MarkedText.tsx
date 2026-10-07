import type { ReactNode } from 'react'

import type { DraftMentionOut } from '@/api/types'
import { DraftMentionMark } from '@/components/share/DraftMentionMark'

type MarkedTextProps = {
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
 * Text with each checked figure that is not plainly supported marked in place: one that
 * differs from today's file, one not in it, or one the provider must not see. Figures
 * that match are left plain unless asked for, since their text usually cites its own
 * sources: the brief's sentences (D12), and a share note the server refused (D25).
 */
export function MarkedText({ text, mentions, from, to, markSupported }: MarkedTextProps) {
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
