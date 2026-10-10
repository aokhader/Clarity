import { CircleCheck, CircleHelp, Info, Lock, TriangleAlert, type LucideIcon } from 'lucide-react'

import type { SentenceVerdict } from '@/api/types'
import { CheckedDraftText } from '@/components/share/CheckedDraftText'
import { LoadError } from '@/components/shared/LoadError'
import type { DraftCheckState } from '@/lib/useCheckedDraft'
import { cn } from '@/lib/utils'

const VERDICT_LINES: Record<SentenceVerdict, { Icon: LucideIcon; tone: string; text: string }> = {
  supported: {
    Icon: CircleCheck,
    tone: 'text-success',
    text: 'Every amount and date found matches what the link shows. The check covers figures only.',
  },
  differs: { Icon: TriangleAlert, tone: 'text-warning', text: 'Some amounts or dates differ from the file.' },
  not_in_file: { Icon: CircleHelp, tone: 'text-muted-foreground', text: 'Some amounts or dates are not in the file.' },
  // A right figure the link does not carry: not a lock and not an error (D37).
  not_on_link: { Icon: Info, tone: 'text-muted-foreground', text: 'Some dates are in the file but not on this link.' },
  do_not_send: {
    Icon: Lock,
    tone: 'text-danger',
    text: "Don't send: it mentions facts this link keeps internal. Remove those sentences to send it.",
  },
  // Not an all-clear: words that reveal an internal fact without a figure are not caught (D17).
  unchecked: {
    Icon: CircleHelp,
    tone: 'text-muted-foreground',
    text: 'No amounts or dates found. The check covers figures only.',
  },
}

const CHECKING = <p className="text-sm text-muted-foreground">Checking amounts and dates against the file…</p>

type DraftCheckViewProps = {
  state: DraftCheckState
  /** Puts edited text back in the editor, for "Use the file's value" and "Remove sentence". */
  onChange: (text: string) => void
  /** Draw the marked text even when no sentence carries an amount or date. */
  alwaysShowText?: boolean
}

/** What the server's check found in a draft: one line for the whole, then the marked text. */
export function DraftCheckView({ state, onChange, alwaysShowText = false }: DraftCheckViewProps) {
  const { checked, current, checking, error, retry } = state
  if (error) return <LoadError what="the check of this draft" error={error} onRetry={retry} />
  if (checked === null) {
    return checking ? CHECKING : null
  }

  const line = VERDICT_LINES[checked.check.verdict]
  const edit = (start: number, end: number, replacement: string) =>
    onChange(checked.text.slice(0, start) + replacement + checked.text.slice(end))
  const showText = alwaysShowText || checked.check.verdict !== 'unchecked'
  return (
    <div className="space-y-3">
      <div role="status" aria-live="polite">
        {checking ? (
          CHECKING
        ) : (
          <p className={cn('flex items-start gap-2 text-sm font-medium', line.tone)}>
            <line.Icon aria-hidden className="mt-0.5 size-4 shrink-0" />
            {line.text}
          </p>
        )}
      </div>
      {showText && (
        <div className={cn('transition-opacity', !current && 'opacity-60')}>
          <CheckedDraftText checked={checked} onEdit={current ? edit : undefined} />
        </div>
      )}
    </div>
  )
}
