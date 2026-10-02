import { useQuery } from '@tanstack/react-query'

import { ApiError, apiGet } from './client'
import type { ProviderPayload, ProviderSourceOut } from './types'

/** True when the link is unknown (404) or expired or withdrawn (410). */
export function isLinkGone(error: Error): boolean {
  return error instanceof ApiError && (error.status === 404 || error.status === 410)
}

function retryUnlessGone(failureCount: number, error: Error): boolean {
  return !isLinkGone(error) && failureCount < 1
}

function linkPath(token: string): string {
  return `/p/${encodeURIComponent(token)}`
}

export function useProviderPayload(token: string) {
  return useQuery({
    queryKey: ['provider', token],
    queryFn: () => apiGet<ProviderPayload>(linkPath(token)),
    // Each fetch records an "opened" event the firm sees, so fetch once per visit.
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    retry: retryUnlessGone,
  })
}

export function useProviderSource(token: string, factId: number | null) {
  return useQuery({
    queryKey: ['provider', token, 'source', factId],
    queryFn: () => apiGet<ProviderSourceOut>(`${linkPath(token)}/facts/${factId}/source`),
    enabled: factId !== null,
    retry: retryUnlessGone,
  })
}
