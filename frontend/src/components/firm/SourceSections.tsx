import { useEffect, useRef } from 'react'

import type { SourceFieldOut, SourceSectionOut } from '@/api/types'
import { HighlightedText } from '@/components/firm/HighlightedText'
import { formatDate, formatMoney } from '@/lib/format'
import { findQuote, plainText } from '@/lib/quote'
import { cn } from '@/lib/utils'

/** Values longer than this take the full width instead of one of two columns. */
const LONG_VALUE = 60

/** Where the quote sits: the record's title, one field of a section, or a section's text. */
type QuoteSpot = { section: number; field: number | null; quote: string } | 'title'

/** The ways a quote may have written this value: as stored in Clio, or as shown. */
function valueForms(field: SourceFieldOut): string[] {
  if (field.amount_cents !== null) {
    const dollars = field.amount_cents / 100
    return [String(dollars), dollars.toFixed(1), dollars.toFixed(2), formatMoney(field.amount_cents)]
  }
  // A checkbox is shown as Yes or No but stored, and quoted, as true or false.
  if (field.value === 'Yes') return ['Yes', 'true']
  if (field.value === 'No') return ['No', 'false']
  return [field.value ?? field.on ?? '']
}

function quotesField(field: SourceFieldOut, quote: string): boolean {
  return valueForms(field).some((form) => findQuote(`${field.label}: ${form}`, quote) !== null)
}

function shownValue(field: SourceFieldOut): string {
  if (field.amount_cents !== null) return formatMoney(field.amount_cents)
  if (field.on !== null) return formatDate(field.on)
  return field.value ?? ''
}

function findInSections(sections: SourceSectionOut[], quote: string): QuoteSpot | null {
  for (const [section, { fields, text }] of sections.entries()) {
    // Facts from a field quote "label: value" or the value alone; this matches both.
    const field = fields.findIndex((f) => quotesField(f, quote))
    if (field >= 0) return { section, field, quote }
    if (text && findQuote(plainText(text), quote)) return { section, field: null, quote }
  }
  return null
}

/** Where the quote is, matched like the pipeline's quote check. */
function locateQuote(sections: SourceSectionOut[], title: string | null, quote: string | null): QuoteSpot | null {
  if (!quote) return null
  const whole = findInSections(sections, quote)
  if (whole || !title) return whole
  if (findQuote(title, quote)) return 'title'
  // A task's quote reads "name: description", and the name is the record's title.
  const titled = findQuote(quote, `${title}:`)
  if (titled === null || titled[0] !== 0) return null
  const rest = quote.slice(titled[1]).trim()
  return rest ? findInSections(sections, rest) : 'title'
}

type SourceSectionsProps = {
  sections: SourceSectionOut[]
  /** The record's title, shown above the sections; a quote may begin with it. */
  title: string | null
  /** The supporting quote, highlighted where it is found and scrolled into view. */
  quote: string | null
}

/** A matter or task record laid out by aspect, each value under its own label. */
export function SourceSections({ sections, title, quote }: SourceSectionsProps) {
  const located = locateQuote(sections, title, quote)
  const spot = located === 'title' ? null : located
  const quotedFieldRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    quotedFieldRef.current?.scrollIntoView({ block: 'center' })
  }, [spot?.section, spot?.field])

  return (
    <div className="space-y-6">
      {quote && located === null && (
        <p className="text-xs font-medium text-warning">The quote could not be located in this record.</p>
      )}
      {sections.map(({ heading, fields, text }, sectionIndex) => (
        <section key={heading} aria-label={heading}>
          <h4 className="border-b pb-1.5 text-xs font-semibold tracking-[0.08em] text-muted-foreground uppercase">
            {heading}
          </h4>
          {fields.length > 0 && (
            <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-3">
              {fields.map((field, fieldIndex) => {
                const quoted = spot?.section === sectionIndex && spot.field === fieldIndex
                return (
                  <div
                    key={`${field.label}-${fieldIndex}`}
                    ref={quoted ? quotedFieldRef : undefined}
                    className={cn(
                      'min-w-0 rounded-md',
                      (field.value?.length ?? 0) > LONG_VALUE && 'col-span-2',
                      quoted && '-mx-2 bg-primary/10 px-2 py-1.5 ring-1 ring-primary/40',
                    )}
                  >
                    <dt className="text-xs text-muted-foreground">
                      {field.label}
                      {quoted && <span className="sr-only"> (the quoted value)</span>}
                    </dt>
                    <dd className="mt-0.5 text-sm leading-snug break-words tabular-nums">{shownValue(field)}</dd>
                  </div>
                )
              })}
            </dl>
          )}
          {text && (
            <div className="mt-3">
              <HighlightedText
                text={text}
                quote={spot?.section === sectionIndex && spot.field === null ? spot.quote : null}
              />
            </div>
          )}
        </section>
      ))}
    </div>
  )
}
