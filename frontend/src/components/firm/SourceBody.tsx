import type { SourceOut } from '@/api/types'
import { DocumentPages } from '@/components/firm/DocumentPages'
import { HighlightedText } from '@/components/firm/HighlightedText'
import { SourceSections } from '@/components/firm/SourceSections'
import { SourceTitle } from '@/components/firm/SourceTitle'
import { formatDate } from '@/lib/format'
import { SOURCE_LABELS } from '@/lib/labels'
import { quotedInTitleOnly } from '@/lib/quote'

type SourceBodyProps = {
  source: SourceOut
  /** The supporting quote, when this is the fact's own source. */
  quote: string | null
  citedPageNo: number | null
}

/**
 * The source's date as the header shows it. A document shows its own date when Clio has
 * one; otherwise only the day it was uploaded is known, which can be years after it was
 * written, so it says so.
 */
function dateLabel(source: SourceOut): string | null {
  if (source.source_type === 'document' && source.document_date) return formatDate(source.document_date)
  if (!source.occurred_on) return null
  const day = formatDate(source.occurred_on)
  return source.source_type === 'document' ? `Uploaded ${day}` : day
}

export function SourceBody({ source, quote, citedPageNo }: SourceBodyProps) {
  const meta = [SOURCE_LABELS[source.source_type], dateLabel(source), source.author].filter(Boolean)
  // An email's facts can come from its subject line rather than its body.
  const quotedTitle =
    source.pages.length === 0 &&
    source.sections.length === 0 &&
    source.text !== null &&
    quotedInTitleOnly(source.text, source.title, quote)
  return (
    <article>
      <p className="text-xs text-muted-foreground">{meta.join(' · ')}</p>
      {source.title && <SourceTitle title={source.title} quote={quotedTitle ? quote : null} />}
      <div className="mt-3">
        {source.pages.length > 0 ? (
          <DocumentPages pages={source.pages} citedPageNo={citedPageNo} quote={quote} />
        ) : source.sections.length > 0 ? (
          <SourceSections sections={source.sections} title={source.title} quote={quote} />
        ) : source.text ? (
          <HighlightedText text={source.text} quote={quotedTitle ? null : quote} />
        ) : (
          <p className="text-sm text-muted-foreground">This source has no readable text.</p>
        )}
      </div>
    </article>
  )
}
