import { useId, useState } from 'react'

import type { KpiValueOut } from '@/api/types'
import { KpiValueRow } from '@/components/firm/KpiValueRow'

/** Entries shown under a lead figure before the rest fold behind a button. */
const SHOWN_UNDER_LEAD = 1

type KpiAlsoOnFileProps = {
  values: KpiValueOut[]
  /** What the entries are, for the button: "limit" and "limits" on the Coverage tile. */
  noun: { one: string; many: string }
}

/**
 * The entries under a tile's lead figure: the first, then a disclosure for the rest. The
 * rest follow the button when shown, so the reader's place and focus stay on it.
 */
export function KpiAlsoOnFile({ values, noun }: KpiAlsoOnFileProps) {
  const [expanded, setExpanded] = useState(false)
  const restId = useId()
  const shown = values.slice(0, SHOWN_UNDER_LEAD)
  const rest = values.slice(SHOWN_UNDER_LEAD)
  return (
    <div className="mt-3 border-t pt-2">
      <ul aria-label="Also on file" className="space-y-1.5">
        {shown.map((value, index) => (
          <KpiValueRow key={value.facts[0]?.id ?? index} value={value} size="small" />
        ))}
      </ul>
      {rest.length > 0 && (
        <>
          <button
            type="button"
            aria-expanded={expanded}
            aria-controls={restId}
            onClick={() => setExpanded((open) => !open)}
            className="mt-1.5 text-xs font-medium text-primary underline-offset-4 hover:underline"
          >
            {expanded ? `Show fewer ${noun.many}` : `${rest.length} more ${rest.length === 1 ? noun.one : noun.many}`}
          </button>
          <ul id={restId} hidden={!expanded} aria-label={`More ${noun.many}`} className="mt-1.5 space-y-1.5">
            {rest.map((value, index) => (
              <KpiValueRow key={value.facts[0]?.id ?? index} value={value} size="small" />
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
