import { useState, type ReactNode } from 'react'
import { useParams } from 'react-router'

import { ApiError } from '@/api/client'
import { isLinkGone, useProviderPayload } from '@/api/provider'
import type { ProviderItemOut } from '@/api/types'
import { LinkUnavailable } from '@/components/share/LinkUnavailable'
import { ProviderPageViewer } from '@/components/share/ProviderPageViewer'
import { ProviderView } from '@/components/share/ProviderView'
import { ProviderViewSkeleton } from '@/components/share/ProviderViewSkeleton'
import { LoadError } from '@/components/shared/LoadError'

/** The provider's view at /p/:token. It renders only what the API released for this link. */
export function ProviderPage() {
  const { token = '' } = useParams()
  const payload = useProviderPayload(token)
  const [viewing, setViewing] = useState<ProviderItemOut | null>(null)

  let body: ReactNode
  if (payload.isPending) {
    body = <ProviderViewSkeleton />
  } else if (payload.isError) {
    body = isLinkGone(payload.error) ? (
      <LinkUnavailable expired={payload.error instanceof ApiError && payload.error.status === 410} />
    ) : (
      <LoadError what="the case status" error={payload.error} onRetry={() => void payload.refetch()} />
    )
  } else {
    body = (
      <>
        <ProviderView payload={payload.data} onOpenSource={setViewing} />
        <ProviderPageViewer token={token} item={viewing} onClose={() => setViewing(null)} />
      </>
    )
  }
  return <main className="mx-auto max-w-2xl px-6 py-10">{body}</main>
}
