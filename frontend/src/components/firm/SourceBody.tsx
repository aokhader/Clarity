import type { SourceOut } from '@/api/types'
import { DocumentPages } from '@/components/firm/DocumentPages'
import { HighlightedText } from '@/components/firm/HighlightedText'
import { SourceSections } from '@/components/firm/SourceSections'
import { formatDate } from '@/lib/format'
import { SOURCE_LABELS } from '@/lib/labels'

type SourceBodyProps = {
  source: SourceOut
  /** The supporting quote, when this is the fact's own source. */
  quote: string | null
  citedPageNo: number | null
}

export function SourceBody({ source, quote, citedPageNo }: SourceBodyProps) {
  const meta = [
    SOURCE_LABELS[source.source_type],
    source.occurred_on ? formatDate(source.occurred_on) : null,
    source.author,
  ].filter(Boolean)
  return (
    <article>
      <p className="text-xs text-muted-foreground">{meta.join(' · ')}</p>
      {source.title && <h3 className="mt-0.5 font-medium">{source.title}</h3>}
      <div className="mt-3">
        {source.pages.length > 0 ? (
          <DocumentPages pages={source.pages} citedPageNo={citedPageNo} quote={quote} />
        ) : source.sections.length > 0 ? (
          <SourceSections sections={source.sections} title={source.title} quote={quote} />
        ) : source.text ? (
          <HighlightedText text={source.text} quote={quote} />
        ) : (
          <p className="text-sm text-muted-foreground">This source has no readable text.</p>
        )}
      </div>
    </article>
  )
}
