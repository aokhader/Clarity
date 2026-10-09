import { Button } from '@/components/ui/button'

type QuoteCalloutProps = {
  quote: string
  /** The document page the quote was read from; null for every other source. */
  pageNo: number | null
  /** Scrolls to the quote where it sits in the record; null when it is not marked there. */
  onShowInRecord: (() => void) | null
}

/** The fact's cited passage, set before the record so it is read first. */
export function QuoteCallout({ quote, pageNo, onShowInRecord }: QuoteCalloutProps) {
  return (
    <figure className="border-l-2 border-primary bg-muted px-4 py-3">
      <figcaption className="text-xs font-semibold tracking-[0.08em] text-muted-foreground uppercase tabular-nums">
        Cited passage{pageNo !== null && ` · page ${pageNo}`}
      </figcaption>
      <blockquote className="mt-1.5 text-base leading-relaxed text-pretty">“{quote}”</blockquote>
      {onShowInRecord && (
        <Button
          variant="link"
          onClick={onShowInRecord}
          className="-mb-2 -ml-2.5 h-10 px-2.5 transition-colors"
        >
          Show in the record
        </Button>
      )}
    </figure>
  )
}
