import { Skeleton } from '@/components/ui/skeleton'

export function ProviderViewSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading the case status" className="space-y-4">
      <Skeleton className="h-4 w-56" />
      <Skeleton className="h-9 w-80" />
      <Skeleton className="h-28 w-full" />
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-40 w-full" />
    </div>
  )
}
