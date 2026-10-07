import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useState } from 'react'

import type { PageRef } from '@/api/types'
import { Button } from '@/components/ui/button'

type DocumentPagesProps = {
  pages: PageRef[]
  /** The page the fact was read from; the viewer opens there. */
  citedPageNo: number | null
  quote: string | null
}

/** A document's rendered pages, opened at the cited page, with the quote above. */
export function DocumentPages({ pages, citedPageNo, quote }: DocumentPagesProps) {
  const citedIndex = Math.max(
    0,
    pages.findIndex((page) => page.page_no === citedPageNo),
  )
  const [index, setIndex] = useState(citedIndex)
  const [unloaded, setUnloaded] = useState<ReadonlySet<number>>(new Set())
  const page = pages[index]
  if (!page) return <p className="text-sm text-muted-foreground">This document has no rendered pages.</p>

  return (
    <div className="space-y-3">
      {quote && (
        <blockquote className="border-l-2 border-primary bg-muted px-3 py-2 text-sm">
          “{quote}”
          {citedPageNo !== null && (
            <footer className="mt-1 text-xs text-muted-foreground">Quoted from page {citedPageNo}</footer>
          )}
        </blockquote>
      )}
      <div className="flex items-center justify-between gap-2">
        <Button variant="outline" size="sm" onClick={() => setIndex(index - 1)} disabled={index === 0}>
          <ChevronLeft aria-hidden />
          Previous
        </Button>
        <span className="flex items-center gap-2 text-sm tabular-nums">
          Page {page.page_no} of {pages.length}
          {index !== citedIndex && (
            <Button variant="link" size="sm" onClick={() => setIndex(citedIndex)}>
              Back to cited page
            </Button>
          )}
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setIndex(index + 1)}
          disabled={index === pages.length - 1}
        >
          Next
          <ChevronRight aria-hidden />
        </Button>
      </div>
      {unloaded.has(page.page_id) ? (
        <p className="rounded-sm border border-dashed px-4 py-12 text-center text-sm text-muted-foreground">
          The image of page {page.page_no} could not be loaded.
        </p>
      ) : (
        <img
          key={page.page_id}
          src={page.image_url}
          alt={`Page ${page.page_no}`}
          onError={() => setUnloaded((previous) => new Set(previous).add(page.page_id))}
          className="w-full rounded-sm border bg-white"
        />
      )}
    </div>
  )
}
