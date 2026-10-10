import { useEffect, useLayoutEffect, useRef, useState } from 'react'

import type { FactOut, FactSourceOut } from '@/api/types'
import { QuoteCallout } from '@/components/firm/QuoteCallout'
import { SourceBody } from '@/components/firm/SourceBody'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { SOURCE_LABELS } from '@/lib/labels'

/** What a record sets on the first element of the quote it marks. */
const QUOTE_MARK = '[data-quote-mark]'

/** A call note records where its quote sits in the transcript; other facts are searched for. */
function quoteSpanOf(fact: FactOut): [number, number] | null {
  if (fact.kind !== 'call_note') return null
  const { quote_start: start, quote_end: end } = fact.value
  return start !== null && end !== null ? [start, end] : null
}

/**
 * The fact's quote, then the cited source, plus a tab for each source that corroborates
 * it. The quote leads, so the drawer opens at the top rather than scrolled to the mark;
 * "Show in the record" goes to the mark when the record has one.
 */
export function FactSourceView({ data }: { data: FactSourceOut }) {
  const { fact, source, corroborating } = data
  const citedTab = String(source.source_id)
  const [tab, setTab] = useState(citedTab)
  const [marked, setMarked] = useState(false)
  const [revealRequests, setRevealRequests] = useState(0)
  const contentRef = useRef<HTMLDivElement>(null)

  // The drawer remounts this view for each fact, and the cited record is always in the
  // page, so whether it marked the quote is known before the first paint.
  useLayoutEffect(() => {
    setMarked(Boolean(contentRef.current?.querySelector(QUOTE_MARK)))
  }, [])

  // An effect rather than the click handler, so a request made from another tab runs once
  // the cited record is shown again.
  useEffect(() => {
    if (revealRequests === 0) return
    const mark = contentRef.current?.querySelector<HTMLElement>(QUOTE_MARK)
    mark?.scrollIntoView({ block: 'center' })
    mark?.focus({ preventScroll: true })
  }, [revealRequests])

  const showInRecord = () => {
    setTab(citedTab)
    setRevealRequests((count) => count + 1)
  }

  const cited = (
    <SourceBody source={source} quote={fact.quote} quoteSpan={quoteSpanOf(fact)} citedPageNo={fact.page_no} />
  )

  return (
    <div ref={contentRef} className="space-y-6">
      {fact.quote && (
        <QuoteCallout
          quote={fact.quote}
          pageNo={source.source_type === 'document' ? fact.page_no : null}
          onShowInRecord={marked ? showInRecord : null}
        />
      )}
      {corroborating.length === 0 ? (
        cited
      ) : (
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList>
            <TabsTrigger value={citedTab}>Cited source</TabsTrigger>
            {corroborating.map((other) => (
              <TabsTrigger key={other.source_id} value={String(other.source_id)}>
                Also in {SOURCE_LABELS[other.source_type]}
              </TabsTrigger>
            ))}
          </TabsList>
          {/* Kept in the page while another tab is open, so the quote's mark is there to go to. */}
          <TabsContent value={citedTab} forceMount className="pt-3 data-[state=inactive]:hidden">
            {cited}
          </TabsContent>
          {corroborating.map((other) => (
            <TabsContent key={other.source_id} value={String(other.source_id)} className="pt-3">
              <SourceBody source={other} quote={null} citedPageNo={null} />
            </TabsContent>
          ))}
        </Tabs>
      )}
    </div>
  )
}
