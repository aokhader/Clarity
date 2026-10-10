import { useState, type ReactNode } from 'react'

import { useMatterProviders, useMatterShares } from '@/api/shares'
import type { ProviderOut, ShareOut } from '@/api/types'
import { ProviderRow } from '@/components/share/ProviderRow'
import { ShareComposer } from '@/components/share/ShareComposer'
import { LoadError } from '@/components/shared/LoadError'
import { Panel } from '@/components/shared/Panel'
import { Skeleton } from '@/components/ui/skeleton'

type ProvidersPanelProps = {
  matterId: number
  /** The firm user sharing, from the user switcher. Null disables sharing. */
  userId: number | null
}

/** The provider's link if it is neither withdrawn nor expired. */
function liveUrl(provider: ProviderOut, shares: ShareOut[], now: Date): string | null {
  const status = provider.share
  if (status === null || status.revoked) return null
  if (status.expires_at !== null && new Date(status.expires_at) <= now) return null
  return shares.find((share) => share.id === status.share_id)?.url ?? null
}

/** Each medical provider's totals and share status, with a Share button per row. */
export function ProvidersPanel({ matterId, userId }: ProvidersPanelProps) {
  const providers = useMatterProviders(matterId)
  const shares = useMatterShares(matterId)
  const [now] = useState(() => new Date())
  const [composing, setComposing] = useState<ProviderOut | null>(null)

  let body: ReactNode
  if (providers.isPending) {
    body = <Skeleton className="h-24 w-full" />
  } else if (providers.isError) {
    body = <LoadError what="the providers" error={providers.error} onRetry={() => void providers.refetch()} />
  } else if (providers.data.length === 0) {
    body = <p className="text-sm text-muted-foreground">No medical providers identified in the file.</p>
  } else {
    body = (
      <ul className="-my-3 divide-y">
        {providers.data.map((provider) => (
          <ProviderRow
            key={provider.contact_id}
            matterId={matterId}
            provider={provider}
            liveUrl={liveUrl(provider, shares.data ?? [], now)}
            onShare={userId === null ? null : () => setComposing(provider)}
            now={now}
          />
        ))}
      </ul>
    )
  }
  return (
    <Panel title="Providers" aside={providers.data?.length}>
      {/* Without the shares, live links would show as unshared, so the failure is stated. */}
      {shares.isError && (
        <div className="mb-4">
          <LoadError what="the share links" error={shares.error} onRetry={() => void shares.refetch()} />
        </div>
      )}
      {body}
      {userId !== null && (
        <ShareComposer matterId={matterId} userId={userId} provider={composing} onClose={() => setComposing(null)} />
      )}
    </Panel>
  )
}
