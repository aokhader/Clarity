import { useId, useRef } from 'react'

import { AskHandle } from '@/components/ask/AskHandle'
import { AskItemChip } from '@/components/ask/AskItemChip'
import { BudgetNote } from '@/components/ask/BudgetNote'
import { Button } from '@/components/ui/button'
import { askRefKey } from '@/lib/askItems'
import { useAskContext } from '@/lib/askState'
import { THREAD_CLOSED } from '@/lib/chatErrors'
import { useAskQuestion } from '@/lib/useAskQuestion'

type ChatComposerProps = {
  matterId: number
  /** Offer the pointing handle, where there are rows to point at (the panel, not the Ask view). */
  withHandle?: boolean
}

/**
 * Write a question, with the items pointed at, and ask it: a follow-up when a thread is
 * open, else a new thread. Enter asks and Shift+Enter starts a new line. Ask is off, with
 * the reason beside it, while the answer is being written or once the day's budget is spent.
 * A closed thread takes no questions (D52): the composer then shows nothing, unless a
 * follow-up was just refused because the thread had closed meanwhile.
 */
export function ChatComposer({ matterId, withHandle = false }: ChatComposerProps) {
  const ask = useAskContext()
  const question = useAskQuestion(matterId)
  const fieldId = useId()
  const reasonId = useId()
  const field = useRef<HTMLTextAreaElement>(null)
  const submit = () => question.submit(ask.draft, { openPanel: false })

  if (question.closed) {
    return question.closedRefusal ? (
      <p role="alert" className="text-sm text-danger">
        {THREAD_CLOSED}
      </p>
    ) : null
  }

  return (
    <form
      aria-label="Ask a question"
      className="space-y-2"
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
    >
      {ask.items.length > 0 && (
        <ul aria-label="Items attached to the question" className="flex flex-wrap gap-1.5">
          {ask.items.map((item) => (
            <li key={askRefKey(item.ref)} className="max-w-full">
              <AskItemChip label={item.label} onRemove={() => ask.removeItem(item.ref)} />
            </li>
          ))}
        </ul>
      )}
      <label htmlFor={fieldId} className="block text-xs font-medium text-muted-foreground">
        {question.following ? 'Follow-up question' : 'Question'}
      </label>
      <div className="flex items-end gap-2">
        {withHandle && <AskHandle onPicked={() => requestAnimationFrame(() => field.current?.focus())} />}
        <textarea
          ref={field}
          id={fieldId}
          rows={2}
          value={ask.draft}
          maxLength={2000}
          onChange={(event) => ask.setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault()
              submit()
            }
          }}
          aria-describedby={question.blocked ? reasonId : undefined}
          className="min-h-16 min-w-0 flex-1 resize-y rounded-md border border-input bg-card px-2.5 py-1.5 text-[15px] leading-snug"
        />
        <Button
          type="submit"
          disabled={question.blocked !== null || question.pending || ask.draft.trim() === ''}
          aria-describedby={question.blocked ? reasonId : undefined}
        >
          {question.pending ? 'Asking…' : 'Ask'}
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">Enter asks; Shift+Enter starts a new line.</p>
      {question.blocked && (
        <p id={reasonId} className="text-sm text-muted-foreground">
          {question.blocked}
        </p>
      )}
      <BudgetNote budget={question.budget} />
      {question.error && (
        <p role="alert" className="text-sm text-danger">
          {question.error}
        </p>
      )}
    </form>
  )
}
