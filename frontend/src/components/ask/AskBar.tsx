import { useEffect, useId, useRef, useState } from 'react'

import { SEARCH_MIN_CHARS, useAskSearch } from '@/api/chat'
import type { FactOut } from '@/api/types'
import { AskHandle } from '@/components/ask/AskHandle'
import { AskItemChip } from '@/components/ask/AskItemChip'
import { BudgetNote } from '@/components/ask/BudgetNote'
import { Button } from '@/components/ui/button'
import { askRefKey, cutLabel, factsRef } from '@/lib/askItems'
import { ASK_BAR_ATTRIBUTE, useAskContext } from '@/lib/askState'
import { STARTERS, starterKindOf } from '@/lib/askStarters'
import { formatDate } from '@/lib/format'
import { KIND_LABELS, SOURCE_LABELS } from '@/lib/labels'
import { useAskQuestion } from '@/lib/useAskQuestion'

/** Search hits listed under the box. */
const HITS_SHOWN = 8

/** Where a hit comes from, as its chip would say it; the chip itself opens once the question is asked. */
function sourceOf(fact: FactOut): string {
  const type = SOURCE_LABELS[fact.source_type]
  return fact.page_no !== null ? `${type} p.${fact.page_no}` : type
}

/**
 * The Ask bar on every firm view but Ask (D49). Typing searches the file's records at
 * once, with no model call; a hit chosen from the list is attached to the question, as
 * is anything pointed at with the handle. The newest item offers questions to start
 * from. Ask sends the question, as a follow-up when a thread is open, and opens the panel.
 *
 * The box is an ARIA combobox: the arrow keys move through the hits, Enter attaches the
 * highlighted one, and Enter with none highlighted asks what is typed.
 */
export function AskBar({ matterId }: { matterId: number }) {
  const ask = useAskContext()
  const question = useAskQuestion(matterId)
  const search = useAskSearch(matterId, ask.draft)
  const [listOpen, setListOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const input = useRef<HTMLInputElement>(null)
  const inputId = useId()
  const listId = useId()
  const reasonId = useId()

  const searching = ask.draft.trim().length >= SEARCH_MIN_CHARS
  const hits = searching ? (search.data ?? []).slice(0, HITS_SHOWN) : []
  const expanded = listOpen && hits.length > 0
  const optionId = (index: number) => `${listId}-${index}`
  const newest = ask.items.at(-1)
  const askOff = question.blocked !== null || question.pending

  // Keep the highlighted hit in view as the arrow keys move through a long list.
  useEffect(() => {
    if (active >= 0) document.getElementById(`${listId}-${active}`)?.scrollIntoView({ block: 'nearest' })
  }, [active, listId])

  const closeList = () => {
    setListOpen(false)
    setActive(-1)
  }

  const attach = (fact: FactOut) => {
    const ref = factsRef([fact, ...fact.restated_by])
    if (ref === null) return
    const label = cutLabel(fact.title)
    ask.addItem({ ref, label, starter: starterKindOf(fact.kind) })
    ask.setDraft('')
    closeList()
    ask.announce(`Attached ${label}.`)
  }

  const submit = (text: string) => {
    closeList()
    question.submit(text, { openPanel: true })
  }

  return (
    <section {...{ [ASK_BAR_ATTRIBUTE]: '' }} aria-label="Ask about this matter" className="rounded-lg border bg-card px-4 py-3">
      <label htmlFor={inputId} className="mb-1 block text-xs font-medium text-muted-foreground">
        Search the file, or point at an item and ask about it
      </label>
      <form
        className="flex items-start gap-2"
        onSubmit={(event) => {
          event.preventDefault()
          submit(ask.draft)
        }}
      >
        <AskHandle onPicked={() => requestAnimationFrame(() => input.current?.focus())} />
        <div className="relative min-w-0 flex-1">
          <input
            ref={input}
            id={inputId}
            type="text"
            role="combobox"
            autoComplete="off"
            maxLength={2000}
            aria-expanded={expanded}
            aria-controls={listId}
            aria-autocomplete="list"
            aria-activedescendant={expanded && active >= 0 ? optionId(active) : undefined}
            aria-describedby={question.blocked ? reasonId : undefined}
            value={ask.draft}
            placeholder="A word from a record, or a question"
            onChange={(event) => {
              ask.setDraft(event.target.value)
              setListOpen(true)
              setActive(-1)
            }}
            onBlur={closeList}
            onKeyDown={(event) => {
              if (event.nativeEvent.isComposing) return
              if (event.key === 'ArrowDown' && hits.length > 0) {
                event.preventDefault()
                setListOpen(true)
                setActive((index) => (index + 1) % hits.length)
              } else if (event.key === 'ArrowUp' && hits.length > 0) {
                event.preventDefault()
                setListOpen(true)
                setActive((index) => (index <= 0 ? hits.length - 1 : index - 1))
              } else if (event.key === 'Enter' && expanded && active >= 0) {
                event.preventDefault()
                attach(hits[active])
              } else if (event.key === 'Escape' && expanded) {
                event.preventDefault()
                closeList()
              }
            }}
            className="h-9 w-full min-w-0 rounded-md border border-input bg-background px-2.5 text-[15px] placeholder:text-muted-foreground"
          />
          {/* Always in the page, so the combobox's aria-controls names an element. */}
          <ul
            id={listId}
            role="listbox"
            aria-label="Records that match"
            hidden={!expanded}
            className="absolute inset-x-0 top-full z-30 mt-1 max-h-80 overflow-y-auto rounded-md border border-input bg-card py-1"
          >
            {hits.map((fact, index) => (
              <li
                key={fact.id}
                id={optionId(index)}
                role="option"
                aria-selected={index === active}
                // Keep focus in the box, so the list does not close before the click lands.
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => attach(fact)}
                className="cursor-pointer px-3 py-1.5 text-sm aria-selected:bg-muted hover:bg-muted"
              >
                <span className="block [overflow-wrap:anywhere]">{fact.title}</span>
                <span className="block text-xs text-muted-foreground tabular-nums">
                  {KIND_LABELS[fact.kind]}
                  {fact.event_date && ` · ${formatDate(fact.event_date)}`} · {sourceOf(fact)}
                </span>
              </li>
            ))}
          </ul>
        </div>
        <Button type="submit" size="lg" disabled={askOff || ask.draft.trim() === ''}>
          {question.pending ? 'Asking…' : 'Ask'}
        </Button>
      </form>
      <p role="status" className="sr-only">
        {expanded ? `${hits.length} ${hits.length === 1 ? 'record matches' : 'records match'}. Use the arrow keys to choose.` : ''}
      </p>

      {ask.items.length > 0 && (
        <ul aria-label="Items attached to the question" className="mt-2 flex flex-wrap gap-1.5">
          {ask.items.map((item) => (
            <li key={askRefKey(item.ref)} className="max-w-full">
              <AskItemChip label={item.label} onRemove={() => ask.removeItem(item.ref)} />
            </li>
          ))}
        </ul>
      )}
      {newest && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <span className="text-xs text-muted-foreground">Ask:</span>
          {STARTERS[newest.starter].map((starter) => (
            <Button
              key={starter}
              variant="outline"
              size="xs"
              // Starters wrap rather than run off a narrow screen.
              className="h-auto min-h-6 py-0.5 text-left whitespace-normal"
              disabled={askOff}
              onClick={() => {
                ask.setDraft(starter)
                submit(starter)
              }}
            >
              {starter}
            </Button>
          ))}
        </div>
      )}

      {(question.following || question.blocked || question.error) && (
        <div className="mt-2 space-y-1 text-sm">
          {question.following && (
            <p className="flex flex-wrap items-center gap-x-2 text-muted-foreground">
              Asking follows up the open question.
              <button type="button" onClick={ask.newQuestion} className="text-primary underline-offset-4 hover:underline">
                Start a new question
              </button>
              {!ask.panelOpen && (
                <button type="button" onClick={ask.openPanel} className="text-primary underline-offset-4 hover:underline">
                  Show the answers
                </button>
              )}
            </p>
          )}
          {question.blocked && (
            <p id={reasonId} className="text-muted-foreground">
              {question.blocked}
            </p>
          )}
          {question.error && (
            <p role="alert" className="text-danger">
              {question.error}
            </p>
          )}
        </div>
      )}
      <div className="mt-1">
        <BudgetNote budget={question.budget} />
      </div>
    </section>
  )
}
