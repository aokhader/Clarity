import { useHealth } from '@/api/ops'
import { StatusRow } from '@/components/StatusRow'
import { Button } from '@/components/ui/button'

export function BackendStatus() {
  const health = useHealth()

  if (health.isPending) {
    return <div className="h-36 animate-pulse rounded-lg bg-muted" aria-label="Checking the API" />
  }

  if (health.isError) {
    return (
      <div role="alert" className="rounded-lg border border-danger/40 bg-danger-soft p-4 text-sm">
        <p>Could not reach the API: {health.error.message}</p>
        <Button variant="outline" size="sm" className="mt-3" onClick={() => void health.refetch()}>
          Retry
        </Button>
      </div>
    )
  }

  const { clio_configured, models_configured } = health.data
  return (
    <dl className="divide-y rounded-lg border bg-card text-sm">
      <StatusRow label="API and database" ok detail="Connected" />
      <StatusRow
        label="Clio credentials"
        ok={clio_configured}
        detail={clio_configured ? 'Set in .env' : 'Missing: set CLIO_CLIENT_ID and CLIO_CLIENT_SECRET in .env'}
      />
      <StatusRow
        label="Model settings"
        ok={models_configured}
        detail={
          models_configured ? 'Set in .env' : 'Missing: set LLM_API_KEY, EXTRACT_MODEL, and MERGE_MODEL in .env'
        }
      />
    </dl>
  )
}
