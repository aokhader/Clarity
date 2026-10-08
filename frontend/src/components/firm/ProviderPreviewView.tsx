import { useState } from 'react'

import { useMatterProviders } from '@/api/shares'
import { ProviderPreview } from '@/components/firm/ProviderPreview'
import { LoadError } from '@/components/shared/LoadError'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

/** The firm's look at the provider side: pick a provider, see exactly what their link would show. */
export function ProviderPreviewView({ matterId }: { matterId: number }) {
  const providers = useMatterProviders(matterId)
  const [chosenId, setChosenId] = useState<number | null>(null)

  if (providers.isPending) return <Skeleton className="h-64 w-full" aria-label="Loading providers" />
  if (providers.isError) {
    return <LoadError what="the providers" error={providers.error} onRetry={() => void providers.refetch()} />
  }
  if (providers.data.length === 0) {
    return <p className="text-sm text-muted-foreground">No medical providers found in the file.</p>
  }

  const selected = providers.data.find((provider) => provider.contact_id === chosenId) ?? providers.data[0]
  return (
    <>
      <section className="rounded-xl border bg-card px-6 py-5">
        <p className="text-[13px] font-medium tracking-[0.14em] text-muted-foreground uppercase">Provider preview</p>
        <p className="mt-2 max-w-2xl text-[15px]">
          Choose a provider to see what a new link would show them with the default settings. The server applies the
          same filter as the provider&apos;s own page, so case value, strategy, negotiations, and internal notes never
          appear here.
        </p>
        <div role="group" aria-label="Provider" className="mt-4 flex flex-wrap gap-2">
          {providers.data.map((provider) => {
            const active = provider.contact_id === selected?.contact_id
            return (
              <button
                key={provider.contact_id}
                type="button"
                aria-pressed={active}
                onClick={() => setChosenId(provider.contact_id)}
                className={cn(
                  'rounded-md border px-3 py-1.5 text-sm font-medium transition-colors',
                  active
                    ? 'border-primary bg-primary text-primary-foreground'
                    : 'border-input bg-card text-foreground hover:bg-muted',
                )}
              >
                {provider.name}
              </button>
            )
          })}
        </div>
      </section>
      {selected && <ProviderPreview key={selected.contact_id} matterId={matterId} providerId={selected.contact_id} />}
    </>
  )
}
