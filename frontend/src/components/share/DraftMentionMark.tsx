import { CircleCheck, CircleHelp, Info, Lock, TriangleAlert } from 'lucide-react'

import type { DraftMentionOut } from '@/api/types'
import { SourceChipList } from '@/components/shared/SourceChipList'
import { formatDate, formatMoney } from '@/lib/format'
import { cn } from '@/lib/utils'

/** The file's value for a "differs" mention, written the way the draft writes it. */
function fileValue(mention: DraftMentionOut): string | null {
  if (mention.kind === 'amount' && mention.file_amount_cents !== null) return formatMoney(mention.file_amount_cents)
  if (mention.kind === 'date' && mention.file_date !== null) return formatDate(mention.file_date)
  return null
}

/** Beyond this many sources, "+N more" stays a count instead of drawing every chip. */
const MAX_EXPANDED_CHIPS = 8

const UNDERLINE: Record<DraftMentionOut['verdict'], string> = {
  supported: 'decoration-success',
  differs: 'decoration-warning decoration-wavy',
  not_in_file: 'decoration-muted-foreground decoration-dotted',
  not_on_link: 'decoration-muted-foreground decoration-dashed',
  do_not_send: 'decoration-danger',
}

type DraftMentionMarkProps = {
  mention: DraftMentionOut
  /** Puts the file's value in place of the mention. Absent while the check is catching up. */
  onUseFileValue?: (value: string) => void
}

/**
 * One amount or date in a draft, marked where it stands: its words underlined, then what
 * the file says about it, with an icon and a word so colour is never the only signal.
 */
export function DraftMentionMark({ mention, onUseFileValue }: DraftMentionMarkProps) {
  const replacement = mention.verdict === 'differs' ? fileValue(mention) : null
  return (
    <span>
      <span className={cn('underline decoration-2 underline-offset-4', UNDERLINE[mention.verdict])}>
        {mention.text}
      </span>{' '}
      <span title={mention.reason} className="inline-flex flex-wrap items-center gap-1 align-middle text-xs whitespace-normal">
        {mention.verdict === 'supported' && (
          <CircleCheck role="img" aria-label="Matches the file" className="size-3.5 text-success" />
        )}
        {mention.verdict === 'differs' && (
          <span className="inline-flex items-center gap-1 font-medium text-warning">
            <TriangleAlert aria-hidden className="size-3.5" />
            Differs{replacement && <>: the file says {replacement}</>}
          </span>
        )}
        {mention.verdict === 'not_in_file' && (
          <span className="inline-flex items-center gap-1 text-muted-foreground">
            <CircleHelp aria-hidden className="size-3.5" />
            Not in file
          </span>
        )}
        {mention.verdict === 'not_on_link' && (
          <span className="inline-flex items-center gap-1 text-muted-foreground">
            <Info aria-hidden className="size-3.5" />
            In the file, not on this link
          </span>
        )}
        {mention.verdict === 'do_not_send' && (
          <span className="inline-flex items-center gap-1 font-medium text-danger">
            <Lock aria-hidden className="size-3.5" />
            Internal
          </span>
        )}
        {/* A date the file states everywhere (an incident date) can cite hundreds of facts:
            one chip opens a source, and the rest stay a count rather than a wall of chips. */}
        {mention.facts.length > 0 && (
          <SourceChipList facts={mention.facts} max={1} expandable={mention.facts.length <= MAX_EXPANDED_CHIPS} />
        )}
        {replacement && onUseFileValue && (
          <button
            type="button"
            onClick={() => onUseFileValue(replacement)}
            className="rounded-sm border border-warning/50 px-1.5 font-medium text-warning hover:bg-warning-soft focus-visible:outline-2 focus-visible:outline-ring"
          >
            Use the file&apos;s value
          </button>
        )}
      </span>
    </span>
  )
}
