import type { ProviderPayload } from '@/api/types'
import { formatDate } from '@/lib/format'

export function ProviderHeader({ payload }: { payload: ProviderPayload }) {
  return (
    <header className="border-b pb-5">
      <div className="flex items-baseline justify-between gap-4 text-sm">
        <p className="font-medium">{payload.firm_name ?? "From your patient's law firm"}</p>
        <p className="tabular-nums text-muted-foreground">Shared {formatDate(payload.shared_on)}</p>
      </div>
      <h1 className="mt-4 font-serif text-3xl">
        {payload.patient_name ? `Patient: ${payload.patient_name}` : 'Case status'}
      </h1>
      <p className="mt-1 text-sm text-muted-foreground">Prepared for {payload.provider_name}</p>
    </header>
  )
}
