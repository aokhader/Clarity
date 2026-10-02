import type { BriefSentenceOut } from '@/api/types'

/**
 * One sentence of the brief, as plain prose. Its citations still decide whether it is
 * shown at all (`Brief`), but the owner chose to keep chips out of the narrative.
 */
export function BriefSentence({ sentence }: { sentence: BriefSentenceOut }) {
  return <span>{sentence.text.trim()} </span>
}
