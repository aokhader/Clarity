import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError, apiGet } from './client'
import type { ProviderOut, ShareCreate, ShareOut } from './types'

/** POST or PATCH JSON under /api, as a firm user. */
async function send<T>(method: 'POST' | 'PATCH', path: string, body: unknown, userId?: number): Promise<T> {
  const url = `/api${path}`
  const headers: Record<string, string> = { Accept: 'application/json', 'Content-Type': 'application/json' }
  if (userId !== undefined) headers['X-User-Id'] = String(userId)
  const response = await fetch(url, { method, headers, body: JSON.stringify(body) })
  if (!response.ok) {
    throw new ApiError(response.status, `${response.status} ${response.statusText} from ${url}`)
  }
  const parsed: unknown = await response.json()
  // The shape is guaranteed by the backend's response schemas, which types.ts mirrors.
  return parsed as T
}

export function useMatterProviders(matterId: number) {
  return useQuery({
    queryKey: ['matters', matterId, 'providers'],
    queryFn: () => apiGet<ProviderOut[]>(`/matters/${matterId}/providers`),
  })
}

export function useMatterShares(matterId: number) {
  return useQuery({
    queryKey: ['matters', matterId, 'shares'],
    queryFn: () => apiGet<ShareOut[]>(`/matters/${matterId}/shares`),
  })
}

function useInvalidateShares(matterId: number) {
  const queryClient = useQueryClient()
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ['matters', matterId, 'providers'] }),
      queryClient.invalidateQueries({ queryKey: ['matters', matterId, 'shares'] }),
    ])
}

export function useCreateShare(matterId: number) {
  const invalidate = useInvalidateShares(matterId)
  return useMutation({
    mutationFn: ({ userId, body }: { userId: number; body: ShareCreate }) =>
      send<ShareOut>('POST', `/matters/${matterId}/shares`, body, userId),
    onSuccess: invalidate,
  })
}
