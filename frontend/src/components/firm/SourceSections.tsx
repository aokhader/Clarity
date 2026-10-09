import type { SourceFieldOut, SourceSectionOut } from '@/api/types'
import { HighlightedText } from '@/components/firm/HighlightedText'
import { formatDate, formatMoney } from '@/lib/format'
import { findQuote, plainText } from '@/lib/quote'
import { cn } from '@/lib/utils'

/** A value longer than this is read as prose under its label rather than in the grid. */
const LONG_VALUE = 60

/** Where the quote sits: the record's title, one field of a section, or a section's text. */
type QuoteSpot = { section: number; field: number | null; quote: string } | 'title'

/** A field with its index in the section, which is how the quote spot names it. */
type PlacedField = { field: SourceFieldOut; index: number }

type FieldGroup = 'short' | 'long'

/**
 * How each group of fields is set. Short values (dates, money, yes or no) share a grid,
 * two columns at the drawer's width and one when narrow; long values follow it as
 * labelled paragraphs. With `groupFields`, this is the one place the layout is chosen,
 * so a single label-left list would replace both here.
 */
const FIELD_LAYOUT: Record<FieldGroup, { list: string; value: string }> = {
  short: {
    list: 'grid grid-cols-[repeat(auto-fit,minmax(14rem,1fr))] gap-x-8 gap-y-4',
    value: 'mt-0.5 text-base leading-snug tabular-nums',
  },
  long: {
    list: 'flex flex-col gap-5',
    value: 'mt-1 max-w-[32em] text-base leading-relaxed text-pretty whitespace-pre-line',
  },
}

/** A section's fields by group, each in its original order and keeping its index. */
function groupFields(fields: SourceFieldOut[]): Record<FieldGroup, PlacedField[]> {
  const placed = fields.map((field, index) => ({ field, index }))
  return {
    short: placed.filter(({ field }) => shownValue(field).length <= LONG_VALUE),
    long: placed.filter(({ field }) => shownValue(field).length > LONG_VALUE),
  }
}

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
  /** The supporting quote, marked where it is found. */
  quote: string | null
}

/** A matter or task record laid out by aspect, each value under its own label. */
export function SourceSections({ sections, title, quote }: SourceSectionsProps) {
  const located = locateQuote(sections, title, quote)
  const spot = located === 'title' ? null : located

  return (
    <div className="space-y-8">
      {quote && located === null && (
        <p className="text-xs font-medium text-warning">The quote could not be located in this record.</p>
      )}
      {sections.map(({ heading, fields, text }, sectionIndex) => {
        const groups = groupFields(fields)
        return (
          <section key={heading} aria-label={heading}>
            <h4 className="border-b pb-1.5 text-xs font-semibold tracking-[0.08em] text-muted-foreground uppercase">
              {heading}
            </h4>
            <div className="mt-4 space-y-6">
              {(['short', 'long'] as const).map((group) =>
                groups[group].length === 0 ? null : (
                  <dl key={group} className={FIELD_LAYOUT[group].list}>
                    {groups[group].map(({ field, index }) => {
                      const quoted = spot?.section === sectionIndex && spot.field === index
                      return (
                        <div
                          key={`${field.label}-${index}`}
                          data-quote-mark={quoted ? '' : undefined}
                          tabIndex={quoted ? -1 : undefined}
                          className={cn(
                            'min-w-0',
                            quoted &&
                              '-mx-2 -my-1.5 rounded-md bg-primary/10 px-2 py-1.5 ring-1 ring-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
                          )}
                        >
                          <dt className="text-[13px] text-muted-foreground">
                            {field.label}
                            {quoted && <span className="sr-only"> (the quoted value)</span>}
                          </dt>
                          <dd className={cn('break-words', FIELD_LAYOUT[group].value)}>{shownValue(field)}</dd>
                        </div>
                      )
                    })}
                  </dl>
                ),
              )}
              {text && (
                <HighlightedText
                  text={text}
                  quote={spot?.section === sectionIndex && spot.field === null ? spot.quote : null}
                />
              )}
            </div>
          </section>
        )
      })}
    </div>
  )
}
