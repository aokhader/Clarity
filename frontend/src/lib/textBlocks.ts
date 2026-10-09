/**
 * Splits a record's plain text into paragraphs and lists so it can be set to be read,
 * without changing a word. Every block points back into the original string by character
 * offsets, so a view shows only slices of it and a quote's span still lands on the same
 * characters. The one thing a view drops is a list line's own marker, which the list's
 * markers replace.
 */

/** One line of text, as `[start, end)` offsets into the original string. */
export type TextLine = {
  /** After any indent and list marker. */
  start: number
  /** Before any trailing whitespace. */
  end: number
  /** Just after the colon of a short "Label:" lead-in, when the line opens with one. */
  labelEnd: number | null
}

/**
 * A paragraph is lines grouped until a blank line or a list line; a list is consecutive
 * list lines of one kind. An ordered list's `start` is its first item's number, so it
 * counts from where the text does.
 */
export type TextBlock =
  | { kind: 'paragraph'; lines: TextLine[] }
  | { kind: 'list'; ordered: false; items: TextLine[] }
  | { kind: 'list'; ordered: true; start: number; items: TextLine[] }

type ListBlock = Extract<TextBlock, { kind: 'list' }>

const LINE_BREAK = /\r\n|\n|\r/g

/** A bullet (-, *, •, –) or a number (1. or 1)), then a space and the item's text. */
const LIST_MARKER = /^[ \t]*(?:([-*•–])|(\d{1,3})[.)])[ \t]+(?=\S)/

const LABEL_MAX_WORDS = 4
const LABEL_MAX_CHARS = 30

/**
 * A capitalised lead-in of plain words, then a colon, a space and more text. The space
 * rules out a time (10:30) and a URL (https://); the plain words rule out a clause that
 * carries a comma or a full stop; the word and length caps rule out most sentences.
 */
const LEAD_IN = /^(\p{Lu}[\p{L}\p{N}'’&/#()-]*(?:[ \t]+[\p{L}\p{N}][\p{L}\p{N}'’&/#()-]*)*):(?=[ \t]+\S)/u

type RawLine = { start: number; end: number }

type ListLine = { ordered: boolean; number: number; line: TextLine }

function splitLines(text: string): RawLine[] {
  const lines: RawLine[] = []
  let start = 0
  for (const lineBreak of text.matchAll(LINE_BREAK)) {
    lines.push({ start, end: lineBreak.index })
    start = lineBreak.index + lineBreak[0].length
  }
  lines.push({ start, end: text.length })
  return lines
}

/** Where a "Label:" lead-in starting at `start` ends, or null when the line has none. */
function labelEndOf(text: string, start: number, end: number): number | null {
  const match = LEAD_IN.exec(text.slice(start, end))
  if (!match) return null
  const label = match[1]
  if (label.length > LABEL_MAX_CHARS || label.split(/[ \t]+/).length > LABEL_MAX_WORDS) return null
  return start + match[0].length
}

/** A line without its first `skip` characters (a list marker), its indent, or trailing whitespace. */
function textLine(text: string, raw: RawLine, skip: number): TextLine {
  let start = raw.start + skip
  let end = raw.end
  while (start < end && /\s/.test(text[start])) start += 1
  while (end > start && /\s/.test(text[end - 1])) end -= 1
  return { start, end, labelEnd: labelEndOf(text, start, end) }
}

function listLine(text: string, raw: RawLine): ListLine | null {
  const marker = LIST_MARKER.exec(text.slice(raw.start, raw.end))
  if (!marker) return null
  const ordered = marker[2] !== undefined
  return { ordered, number: ordered ? Number(marker[2]) : 0, line: textLine(text, raw, marker[0].length) }
}

/**
 * Whether a list line carries on the list before it. A number that does not follow on
 * starts a new list, so every number shown is the one in the text.
 */
function continues(list: ListBlock, item: ListLine, previousNumber: number): boolean {
  if (list.ordered !== item.ordered) return false
  return !item.ordered || item.number === previousNumber + 1
}

export function parseTextBlocks(text: string): TextBlock[] {
  const blocks: TextBlock[] = []
  // True while the line before was not blank, so this line may join the last block.
  let open = false
  let previousNumber = 0
  for (const raw of splitLines(text)) {
    if (text.slice(raw.start, raw.end).trim() === '') {
      open = false
      continue
    }
    const last = blocks.at(-1)
    const item = listLine(text, raw)
    if (item) {
      if (open && last?.kind === 'list' && continues(last, item, previousNumber)) last.items.push(item.line)
      else if (item.ordered) blocks.push({ kind: 'list', ordered: true, start: item.number, items: [item.line] })
      else blocks.push({ kind: 'list', ordered: false, items: [item.line] })
      previousNumber = item.number
    } else if (open && last?.kind === 'paragraph') {
      last.lines.push(textLine(text, raw, 0))
    } else {
      blocks.push({ kind: 'paragraph', lines: [textLine(text, raw, 0)] })
    }
    open = true
  }
  return blocks
}
