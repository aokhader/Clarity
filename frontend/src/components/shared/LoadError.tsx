import { Button } from '@/components/ui/button'

type LoadErrorProps = {
  /** What failed to load, as a noun phrase: "the action board". */
  what: string
  error: Error
  onRetry: () => void
}

export function LoadError({ what, error, onRetry }: LoadErrorProps) {
  return (
    <div role="alert" className="flex items-center justify-between gap-3 rounded-md border border-danger/40 bg-danger-soft px-3 py-2 text-sm">
      <span>
        Could not load {what}. <span className="text-muted-foreground">{error.message}</span>
      </span>
      <Button variant="outline" size="xs" onClick={onRetry}>
        Retry
      </Button>
    </div>
  )
}
