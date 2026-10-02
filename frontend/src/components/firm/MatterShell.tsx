import type { ReactNode } from 'react'

import { ApiError } from '@/api/client'
import { useMatterHeader } from '@/api/matters'
import type { MatterHeaderOut } from '@/api/types'
import { DigestPrompt } from '@/components/firm/DigestPrompt'
import { MatterHeader } from '@/components/firm/MatterHeader'
import { LoadError } from '@/components/shared/LoadError'
import { Skeleton } from '@/components/ui/skeleton'

type MatterShellProps = {
  matterId: number
  /** The current view, rendered once the header has loaded and the matter is digested. */
  children: (header: MatterHeaderOut) => ReactNode
}

export function MatterShell({ matterId, children }: MatterShellProps) {
  const header = useMatterHeader(matterId)

  if (header.isPending) {
    return (
      <div aria-label="Loading the matter" className="space-y-4">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-96 w-full" />
      </div>
    )
  }

  if (header.isError) {
    if (header.error instanceof ApiError && header.error.status === 404) {
      return (
        <p className="py-16 text-center text-muted-foreground">
          Matter {matterId} has not been synced from Clio.
        </p>
      )
    }
    return <LoadError what="the matter" error={header.error} onRetry={() => void header.refetch()} />
  }

  if (!header.data.digested) {
    return (
      <div className="space-y-6">
        <MatterHeader header={header.data} />
        <DigestPrompt />
      </div>
    )
  }
  return children(header.data)
}
