import { useState } from 'react'

import { useRevokeShare } from '@/api/shares'
import type { ProviderOut } from '@/api/types'
import { CopyLinkButton } from '@/components/share/CopyLinkButton'
import { SendUpdateDialog } from '@/components/share/SendUpdateDialog'
import { ShareStatus } from '@/components/share/ShareStatus'
import { Button } from '@/components/ui/button'
import { formatMoney } from '@/lib/format'

type ProviderRowProps = {
  matterId: number
  provider: ProviderOut
  /** The provider's live link, if one exists. */
  liveUrl: string | null
  /** Opens the share composer. Null while no firm user is chosen: a share records who made it. */
  onShare: (() => void) | null
  now: Date
}

function count(n: number, noun: string): string {
  return `${n} ${noun}${n === 1 ? '' : 's'}`
}

export function ProviderRow({ matterId, provider, liveUrl, onShare, now }: ProviderRowProps) {
  const revoke = useRevokeShare(matterId)
  const [confirming, setConfirming] = useState(false)
  const shareId = provider.share?.share_id

  return (
    <li className="py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 text-sm">
          <p className="font-medium leading-snug">{provider.name}</p>
          {provider.role_label && <p className="text-xs text-muted-foreground">{provider.role_label}</p>}
          <p className="mt-1 tabular-nums">
            {/* Null means no bill with an amount is on file, which is not a zero bill (D16). */}
            {provider.billed_cents === null ? 'No bills on file' : `Billed ${formatMoney(provider.billed_cents)}`} ·{' '}
            {count(provider.records_received, 'record')}
            {provider.open_requests > 0 && ` · ${count(provider.open_requests, 'open request')}`}
          </p>
          <p className="mt-0.5 text-xs">
            <ShareStatus share={provider.share} now={now} />
          </p>
        </div>
        {liveUrl !== null && shareId !== undefined ? (
          <div className="flex shrink-0 flex-col items-end gap-1.5">
            <SendUpdateDialog shareId={shareId} url={liveUrl} providerName={provider.name} />
            <CopyLinkButton url={liveUrl} />
            <Button
              variant={confirming ? 'destructive' : 'ghost'}
              size="xs"
              disabled={revoke.isPending}
              onClick={() =>
                confirming ? revoke.mutate(shareId, { onSuccess: () => setConfirming(false) }) : setConfirming(true)
              }
              onBlur={() => setConfirming(false)}
            >
              {confirming ? 'Confirm withdraw' : 'Withdraw link'}
            </Button>
          </div>
        ) : (
          <Button
            size="sm"
            disabled={onShare === null}
            onClick={onShare ?? undefined}
            title={onShare === null ? 'Choose a firm user to share' : `Share case status with ${provider.name}`}
          >
            Share
          </Button>
        )}
      </div>
      {revoke.isError && (
        <p role="alert" className="mt-2 text-xs text-danger">
          Could not withdraw the link. {revoke.error.message}
        </p>
      )}
    </li>
  )
}
