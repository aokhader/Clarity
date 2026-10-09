import { useEffect, useId, useRef, useState } from 'react'

import { SEARCH_MIN_CHARS, useAskSearch } from '@/api/chat'
import type { FactOut } from '@/api/types'
import { AskAttached } from '@/components/ask/AskAttached'
import { AskHandle } from '@/components/ask/AskHandle'
import { BudgetNote } from '@/components/ask/BudgetNote'
import { Button } from '@/components/ui/button'
import { cutLabel, factsRef } from '@/lib/askItems'
import { ASK_BAR_ATTRIBUTE, useAskContext } from '@/lib/askState'
import { starterKindOf } from '@/lib/askStarters'
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
 * is anything pointed at with the handle. Ask sends the question, as a follow-up when a
 * thread is open, and opens the panel.
 *
 * At rest it is one line, the handle, the box and Ask, so it costs the Overview's first
 * screen little (D50). What it does is the box's description, not a line under it; the
 * attached items and their starter questions take a second line only while there are any.
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
  const hintId = useId()

  const searching = ask.draft.trim().length >= SEARCH_MIN_CHARS
  const hits = searching ? (search.data ?? []).slice(0, HITS_SHOWN) : []
  const expanded = listOpen && hits.length > 0
  const optionId = (index: number) => `${listId}-${index}`
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
    <section {...{ [ASK_BAR_ATTRIBUTE]: '' }} aria-label="Ask about this matter" className="flex flex-col gap-2">
      <form
        className="flex flex-wrap items-center gap-2"
        onSubmit={(event) => {
          event.preventDefault()
          submit(ask.draft)
        }}
      >
        <AskHandle onPicked={() => requestAnimationFrame(() => input.current?.focus())} />
        {/* Grows to fill the line; below its basis the controls after it wrap instead. */}
        <div className="relative min-w-0 grow basis-28">
          <label htmlFor={inputId} className="sr-only">
            Search the file or ask
          </label>
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
            aria-describedby={question.blocked ? `${hintId} ${reasonId}` : hintId}
            value={ask.draft}
            placeholder={question.following ? 'Search, or follow up the open question' : 'Search the file, or ask a question'}
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
            className="h-9 w-full min-w-0 rounded-md border border-input bg-card px-2.5 text-[15px] placeholder:text-muted-foreground"
          />
          {/* Always in the page, so the combobox's aria-controls names an element. It drops over the view, never pushing it. */}
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
          {question.pending ? 'Asking…' : question.answering ? 'Answering…' : 'Ask'}
        </Button>
        {question.following && (
          <span className="flex flex-wrap items-center gap-x-3 text-sm">
            <button type="button" onClick={ask.newQuestion} className="text-primary underline-offset-4 hover:underline">
              Start a new question
            </button>
            {!ask.panelOpen && (
              <button type="button" onClick={ask.openPanel} className="text-primary underline-offset-4 hover:underline">
                Show the answers
              </button>
            )}
          </span>
        )}
      </form>

      {/* What the bar does, said to screen readers rather than shown under it. */}
      <span id={hintId} className="sr-only">
        {question.following ? 'Asking follows up the open question. ' : ''}
        Type a word to find records and attach one, or type a question and press Ask. The handle before the box
        points at an item on the page to ask about it.
      </span>
      <p role="status" className="sr-only">
        {expanded ? `${hits.length} ${hits.length === 1 ? 'record matches' : 'records match'}. Use the arrow keys to choose.` : ''}
      </p>

      <AskAttached onStart={submit} disabled={askOff} />
      {/* A spent budget lasts the day, so it is said in sight; a passing reason is only described. */}
      {question.blocked && (
        <p id={reasonId} className={question.spent ? 'text-sm text-muted-foreground' : 'sr-only'}>
          {question.blocked}
        </p>
      )}
      {question.error && (
        <p role="alert" className="text-sm text-danger">
          {question.error}
        </p>
      )}
      <BudgetNote budget={question.budget} />
    </section>
  )
}
