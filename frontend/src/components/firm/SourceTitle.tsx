import { findQuote } from '@/lib/quote'

type SourceTitleProps = {
  title: string
  /** Marked when the fact was read from the title, as from an email's subject line. */
  quote: string | null
}

export function SourceTitle({ title, quote }: SourceTitleProps) {
  const span = quote ? findQuote(title, quote) : null
  return (
    <h3 className="mt-1 text-base font-semibold text-balance">
      {span ? (
        <>
          {title.slice(0, span[0])}
          <mark
            data-quote-mark=""
            tabIndex={-1}
            className="rounded-sm bg-primary/10 px-0.5 text-foreground ring-1 ring-primary box-decoration-clone focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
          >
            {title.slice(span[0], span[1])}
          </mark>
          {title.slice(span[1])}
        </>
      ) : (
        title
      )}
    </h3>
  )
}
