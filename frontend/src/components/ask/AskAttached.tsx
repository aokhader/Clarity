import { AskItemChip } from '@/components/ask/AskItemChip'
import { Button } from '@/components/ui/button'
import { askRefKey } from '@/lib/askItems'
import { useAskContext } from '@/lib/askState'
import { STARTERS } from '@/lib/askStarters'

type AskAttachedProps = {
  /** Asks a starter question at once. */
  onStart: (question: string) => void
  /** Ask is off, so the starters are too. */
  disabled: boolean
}

/**
 * The Ask bar's second line, there only while something is attached (D50): the items,
 * each with a way to drop it, then the questions the newest one offers to start from.
 * Removing the last item takes the line away.
 */
export function AskAttached({ onStart, disabled }: AskAttachedProps) {
  const ask = useAskContext()
  const newest = ask.items.at(-1)
  if (newest === undefined) return null

  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5">
      <ul aria-label="Items attached to the question" className="flex max-w-full flex-wrap gap-1.5">
        {ask.items.map((item) => (
          <li key={askRefKey(item.ref)} className="max-w-full">
            <AskItemChip label={item.label} onRemove={() => ask.removeItem(item.ref)} />
          </li>
        ))}
      </ul>
      {/* Takes the rest of the line, so the starters wrap one by one rather than as a block. */}
      <div role="group" aria-label="Questions to start from" className="flex min-w-0 grow basis-64 flex-wrap items-center gap-1.5">
        <span className="text-xs text-muted-foreground">Ask:</span>
        {STARTERS[newest.starter].map((starter) => (
          <Button
            key={starter}
            variant="outline"
            size="xs"
            // Starters wrap rather than run off a narrow screen.
            className="h-auto min-h-6 py-0.5 text-left whitespace-normal"
            disabled={disabled}
            onClick={() => {
              ask.setDraft(starter)
              onStart(starter)
            }}
          >
            {starter}
          </Button>
        ))}
      </div>
    </div>
  )
}
