import { useCreateShare } from '@/api/shares'
import type { ProviderOut } from '@/api/types'
import { CopyLinkButton } from '@/components/share/CopyLinkButton'
import { ShareStatus } from '@/components/share/ShareStatus'
import { Button } from '@/components/ui/button'
import { formatMoney } from '@/lib/format'

type ProviderRowProps = {
  matterId: number
  provider: ProviderOut
  /** The provider's live link, if one exists. */
  liveUrl: string | null
  /** The firm user sharing. Null disables sharing, since a share records who made it. */
  userId: number | null
  now: Date
}

function count(n: number, noun: string): string {
  return `${n} ${noun}${n === 1 ? '' : 's'}`
}

export function ProviderRow({ matterId, provider, liveUrl, userId, now }: ProviderRowProps) {
  const create = useCreateShare(matterId)
  return (
    <li className="py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 text-sm">
          <p className="font-medium leading-snug">{provider.name}</p>
          {provider.role_label && <p className="text-xs text-muted-foreground">{provider.role_label}</p>}
          <p className="mt-1 tabular-nums">
            Billed {formatMoney(provider.billed_cents)} · {count(provider.records_received, 'record')}
            {provider.open_requests > 0 && ` · ${count(provider.open_requests, 'open request')}`}
          </p>
          <p className="mt-0.5 text-xs">
            <ShareStatus share={provider.share} now={now} />
          </p>
        </div>
        {liveUrl !== null ? (
          <CopyLinkButton url={liveUrl} />
        ) : (
          <Button
            size="sm"
            disabled={userId === null || create.isPending}
            onClick={() =>
              userId !== null && create.mutate({ userId, body: { provider_contact_id: provider.contact_id } })
            }
            title={userId === null ? 'Choose a firm user to share' : `Share case status with ${provider.name}`}
          >
            {create.isPending ? 'Sharing…' : 'Share'}
          </Button>
        )}
      </div>
      {create.isError && (
        <p role="alert" className="mt-2 text-xs text-danger">
          Could not create the link. {create.error.message}
        </p>
      )}
    </li>
  )
}
