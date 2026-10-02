import { useEffect, useRef } from 'react'

import { findQuote, plainText } from '@/lib/quote'

type HighlightedTextProps = {
  text: string
  /** Highlighted and scrolled into view when found. */
  quote: string | null
}

export function HighlightedText({ text, quote }: HighlightedTextProps) {
  const markRef = useRef<HTMLElement>(null)
  const readable = plainText(text)
  const span = quote ? findQuote(readable, quote) : null

  useEffect(() => {
    markRef.current?.scrollIntoView({ block: 'center' })
  }, [readable, quote])

  return (
    <>
      {quote && span === null && (
        <p className="mb-2 text-xs font-medium text-warning">The quote could not be located in this text.</p>
      )}
      <div className="whitespace-pre-wrap text-sm leading-relaxed">
        {span ? (
          <>
            {readable.slice(0, span[0])}
            <mark ref={markRef} className="rounded-sm bg-primary/10 px-0.5 text-foreground ring-1 ring-primary/40">
              {readable.slice(span[0], span[1])}
            </mark>
            {readable.slice(span[1])}
          </>
        ) : (
          readable
        )}
      </div>
    </>
  )
}
