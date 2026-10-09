import type { AskItemRef } from '@/api/types'
import type { StarterKind } from '@/lib/askStarters'

/** An item attached to the question being written: what is sent, and how its chip reads here. */
export type AskItem = {
  ref: AskItemRef
  /** Read from the screen for the chip; the server labels the stored turn itself. */
  label: string
  starter: StarterKind
}

/** The server takes at most this many items with a question. */
export const MAX_ASK_ITEMS = 8
/** And at most this many facts in one item. */
const MAX_FACTS_PER_ITEM = 50
/** A chip's label is cut to this many characters. */
const LABEL_CHARS = 60

/**
 * The item for some facts: the one a row shows, then those that restate it, without
 * repeats and at most the server's limit. None gives no item, so the row is no target.
 */
export function factsRef(facts: readonly { id: number }[]): AskItemRef | null {
  const ids = [...new Set(facts.map((fact) => fact.id))].slice(0, MAX_FACTS_PER_ITEM)
  return ids.length > 0 ? { kind: 'facts', fact_ids: ids } : null
}

/** One string per distinct item, so the same row pointed at twice is attached once. */
export function askRefKey(ref: AskItemRef): string {
  switch (ref.kind) {
    case 'facts':
      return `facts:${[...ref.fact_ids].sort((a, b) => a - b).join(',')}`
    case 'source':
      return `source:${ref.source_id}`
    case 'provider':
      return `provider:${ref.contact_id}`
    case 'call':
      return `call:${ref.call_id}`
    case 'kpi':
      return `kpi:${ref.name}`
    case 'stage':
      return 'stage'
  }
}

/** Marks text inside a target that is not part of its label, such as its source chips. */
export const ASK_SKIP_ATTRIBUTE = 'data-ask-skip'

/**
 * A pointed-at element's words, for its chip: its text with source chips and hidden
 * marks left out, the pieces spaced, and cut to LABEL_CHARS.
 */
export function labelOfElement(element: HTMLElement): string {
  const pieces: string[] = []
  const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT)
  for (let node = walker.nextNode(); node !== null; node = walker.nextNode()) {
    const parent = node.parentElement
    if (parent?.closest(`[${ASK_SKIP_ATTRIBUTE}], [aria-hidden="true"], .sr-only`)) continue
    const text = node.textContent?.trim()
    if (text) pieces.push(text)
  }
  const label = pieces.join(' ').replace(/\s+/g, ' ').trim()
  return label.length > LABEL_CHARS ? `${label.slice(0, LABEL_CHARS - 1).trimEnd()}…` : label || 'Item'
}

/** What a target carries in its `data-ask-item` attribute. */
type AskTargetData = { ref: AskItemRef; starter: StarterKind }

export function encodeAskTarget(ref: AskItemRef, starter: StarterKind): string {
  return JSON.stringify({ ref, starter } satisfies AskTargetData)
}

/** The item an element marks as a target, read back as written by encodeAskTarget. */
export function askItemOfElement(element: HTMLElement): AskItem | null {
  const raw = element.getAttribute('data-ask-item')
  if (raw === null) return null
  try {
    // Written by encodeAskTarget in this page, never by the server or the user.
    const { ref, starter } = JSON.parse(raw) as AskTargetData
    return { ref, starter, label: labelOfElement(element) }
  } catch {
    return null
  }
}
