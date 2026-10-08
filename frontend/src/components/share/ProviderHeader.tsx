import type { ProviderPayload } from '@/api/types'
import { formatDate } from '@/lib/format'

type ProviderHeaderProps = {
  payload: ProviderPayload
  /** h1 on the provider's own page; h2 where a firm page shows it as a preview. */
  level: 1 | 2
}

export function ProviderHeader({ payload, level }: ProviderHeaderProps) {
  const Heading = level === 1 ? 'h1' : 'h2'
  return (
    <header className="border-b pb-5">
      <div className="flex items-baseline justify-between gap-4 text-sm">
        <p className="font-medium">{payload.firm_name ?? "From your patient's law firm"}</p>
        <p className="tabular-nums text-muted-foreground">Shared {formatDate(payload.shared_on)}</p>
      </div>
      <Heading className="mt-4 font-serif text-3xl">
        {payload.patient_name ? `Patient: ${payload.patient_name}` : 'Case status'}
      </Heading>
      <p className="mt-1 text-sm text-muted-foreground">Prepared for {payload.provider_name}</p>
    </header>
  )
}
