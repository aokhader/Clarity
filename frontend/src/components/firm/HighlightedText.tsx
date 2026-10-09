import { Fragment, type ReactNode } from 'react'

import { findQuote, plainText } from '@/lib/quote'
import { parseTextBlocks, type TextLine } from '@/lib/textBlocks'

type HighlightedTextProps = {
  text: string
  /** Marked where it is found. */
  quote: string | null
  /**
   * Where the quote sits, when the fact recorded it, as a call note does. Used only while
   * it still holds the quote; otherwise the quote is searched for.
   */
  quoteSpan?: [number, number] | null
}

const MARK_CLASS =
  'rounded-sm bg-primary/10 px-0.5 text-foreground ring-1 ring-primary box-decoration-clone focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring'

const LIST_CLASS = 'space-y-1 pl-5 marker:text-muted-foreground'

function overlaps(line: TextLine, span: [number, number]): boolean {
  return span[0] < line.end && span[1] > line.start
}

/**
 * A record's text in paragraphs and lists, with the quote marked. Everything shown is a
 * slice of the text, so the quote's span holds. The mark is cut where the quote crosses
 * a line or a list item, and only its first piece is the target of "Show in the record".
 */
export function HighlightedText({ text, quote, quoteSpan = null }: HighlightedTextProps) {
  const readable = plainText(text)
  const exact = quoteSpan !== null && quote !== null && readable.slice(...quoteSpan) === quote
  const span = exact ? quoteSpan : quote ? findQuote(readable, quote) : null
  const blocks = parseTextBlocks(readable)
  const lines = blocks.flatMap((block) => (block.kind === 'paragraph' ? block.lines : block.items))
  const firstMarked = span === null ? undefined : lines.find((line) => overlaps(line, span))

  /** `[from, to)` of a line, with the part inside its "Label:" lead-in in bold. */
  const labelled = (line: TextLine, from: number, to: number): ReactNode => {
    if (line.labelEnd === null || from >= line.labelEnd) return readable.slice(from, to)
    const split = Math.min(to, line.labelEnd)
    return (
      <>
        <strong className="font-semibold">{readable.slice(from, split)}</strong>
        {readable.slice(split, to)}
      </>
    )
  }

  const renderLine = (line: TextLine): ReactNode => {
    if (span === null || !overlaps(line, span)) return labelled(line, line.start, line.end)
    const markStart = Math.max(line.start, span[0])
    const markEnd = Math.min(line.end, span[1])
    const first = line === firstMarked
    return (
      <>
        {labelled(line, line.start, markStart)}
        <mark className={MARK_CLASS} data-quote-mark={first ? '' : undefined} tabIndex={first ? -1 : undefined}>
          {labelled(line, markStart, markEnd)}
        </mark>
        {labelled(line, markEnd, line.end)}
      </>
    )
  }

  return (
    <>
      {quote && span === null && (
        <p className="mb-2 text-xs font-medium text-warning">The quote could not be located in this text.</p>
      )}
      {/* About 68 characters to a line. The sans averages about 0.47em a character, while
          68ch (68 zeros) measured some 90 in the drawer. */}
      <div className="max-w-[32em] space-y-4 text-base leading-relaxed">
        {blocks.map((block) => {
          if (block.kind === 'paragraph') {
            return (
              <p key={block.lines[0].start} className="text-pretty">
                {block.lines.map((line, index) => (
                  <Fragment key={line.start}>
                    {index > 0 && <br />}
                    {renderLine(line)}
                  </Fragment>
                ))}
              </p>
            )
          }
          const items = block.items.map((line) => (
            <li key={line.start} className="pl-1 text-pretty">
              {renderLine(line)}
            </li>
          ))
          return block.ordered ? (
            <ol key={block.items[0].start} start={block.start} className={`list-decimal ${LIST_CLASS}`}>
              {items}
            </ol>
          ) : (
            <ul key={block.items[0].start} className={`list-disc ${LIST_CLASS}`}>
              {items}
            </ul>
          )
        })}
      </div>
    </>
  )
}
