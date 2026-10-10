import type { ReactNode } from 'react'

import { ApiError } from '@/api/client'
import { useMatterHeader } from '@/api/matters'
import type { MatterHeaderOut } from '@/api/types'
import { DigestPrompt } from '@/components/firm/DigestPrompt'
import { MatterIdentity } from '@/components/firm/MatterIdentity'
import { LoadError } from '@/components/shared/LoadError'
import { Loading } from '@/components/shared/Loading'
import { Skeleton } from '@/components/ui/skeleton'

type MatterShellProps = {
  matterId: number
  /** The view on screen, named in the breadcrumb and the tab's title. */
  viewLabel: string
  /** The current view, rendered under the identity once the matter is digested. */
  children: (header: MatterHeaderOut) => ReactNode
}

/** The matter's identity over the current view, in every state that has the header, so each page has its h1. */
export function MatterShell({ matterId, viewLabel, children }: MatterShellProps) {
  const header = useMatterHeader(matterId)

  if (header.isPending) {
    return (
      <Loading label="Loading the matter" className="space-y-4">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-96 w-full" />
      </Loading>
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

  return (
    <>
      <MatterIdentity header={header.data} viewLabel={viewLabel} />
      {header.data.digested ? children(header.data) : <DigestPrompt />}
    </>
  )
}
