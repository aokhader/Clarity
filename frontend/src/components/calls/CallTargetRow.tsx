import type { CallRole, CallTargetOut } from '@/api/types'
import { SourceChip } from '@/components/shared/SourceChip'
import { Button } from '@/components/ui/button'
import { factsRef } from '@/lib/askItems'
import { useAskTarget } from '@/lib/useAskTarget'

const ROLE_LABELS: Record<CallRole, string> = {
  client: 'Client',
  provider: 'Provider',
  insurer: 'Insurer',
  other: 'Other',
}

/** The server counts the days; zero is today, and null means no contact was found. */
function lastContactText(days: number | null): string {
  if (days === null) return 'No contact found in the file'
  if (days === 0) return 'Last contact today'
  return `Last contact ${days} ${days === 1 ? 'day' : 'days'} ago`
}

type CallTargetRowProps = {
  target: CallTargetOut
  chosen: boolean
  /** Null while another call is on. */
  onChoose: (() => void) | null
}

/** Someone to call: why, with the item's source, when they were last reached, and their number. */
export function CallTargetRow({ target, chosen, onChoose }: CallTargetRowProps) {
  const askTarget = useAskTarget(target.reason_fact && factsRef([target.reason_fact]), 'fact')
  return (
    <li {...askTarget} className="flex items-start justify-between gap-3 py-3">
      <div className="min-w-0 space-y-0.5 text-sm">
        <p className="font-medium leading-snug">{target.name ?? 'Name not in file'}</p>
        <p className="text-xs text-muted-foreground">{ROLE_LABELS[target.role]}</p>
        {target.reason && (
          <p>
            {target.reason} {target.reason_fact && <SourceChip fact={target.reason_fact} />}
          </p>
        )}
        {/* A day count is shown only with the record behind it (rule 3, D23). */}
        {(target.last_contact_days === null || target.last_contact_fact) && (
          <p className="text-xs text-muted-foreground">
            {lastContactText(target.last_contact_days)}{' '}
            {target.last_contact_fact && <SourceChip fact={target.last_contact_fact} />}
          </p>
        )}
        <p className="text-xs">
          {target.phone ? (
            <>
              <span className="tabular-nums">{target.phone}</span>
              {target.phone_source === 'entered' && <span className="text-muted-foreground"> · typed in Clarity</span>}
            </>
          ) : (
            <span className="text-muted-foreground">No number in Clio</span>
          )}
        </p>
      </div>
      <Button
        size="sm"
        variant={chosen ? 'default' : 'outline'}
        aria-pressed={chosen}
        disabled={onChoose === null}
        onClick={onChoose ?? undefined}
      >
        Call
      </Button>
    </li>
  )
}
