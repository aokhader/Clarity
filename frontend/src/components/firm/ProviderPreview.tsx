import { useDraftPreview } from '@/api/shares'
import { ProviderView } from '@/components/share/ProviderView'
import { LoadError } from '@/components/shared/LoadError'
import { Skeleton } from '@/components/ui/skeleton'
import { useSourceDrawer } from '@/lib/useSourceDrawer'

/**
 * What one provider would see on a new link with the default settings. The payload comes
 * from the same server-side filter as the provider's own page, so nothing internal reaches
 * the browser here either. A bill's or record's "View page" opens the firm's source drawer.
 */
export function ProviderPreview({ matterId, providerId }: { matterId: number; providerId: number }) {
  const preview = useDraftPreview(matterId, { provider_contact_id: providerId })
  const drawer = useSourceDrawer()
  if (preview.isPending) {
    return (
      <div className="space-y-4" aria-label="Loading the provider preview">
        <Skeleton className="h-24" />
        <Skeleton className="h-40" />
      </div>
    )
  }
  if (preview.isError) {
    return <LoadError what="the provider preview" error={preview.error} onRetry={() => void preview.refetch()} />
  }
  return <ProviderView payload={preview.data.payload} onOpenSource={(item) => drawer.open(item.fact_id)} />
}
