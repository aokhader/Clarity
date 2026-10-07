import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError, apiGet } from './client'
import type {
  DraftCheckIn,
  DraftCheckOut,
  DraftShareCheckIn,
  ProviderOut,
  ShareCreate,
  ShareOut,
  SharePreviewOut,
} from './types'

/** POST or PATCH JSON under /api, as a firm user. */
async function send<T>(method: 'POST' | 'PATCH', path: string, body?: unknown, userId?: number): Promise<T> {
  const url = `/api${path}`
  const headers: Record<string, string> = { Accept: 'application/json', 'Content-Type': 'application/json' }
  if (userId !== undefined) headers['X-User-Id'] = String(userId)
  const response = await fetch(url, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) })
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

/** What a share with this body would release, before any link exists. */
export function useDraftPreview(matterId: number, body: ShareCreate) {
  return useQuery({
    queryKey: ['matters', matterId, 'share-draft', body],
    queryFn: () => send<SharePreviewOut>('POST', `/matters/${matterId}/shares/preview`, body),
    // Keep showing the last preview while the next one loads, so toggling does not flash.
    placeholderData: keepPreviousData,
  })
}

/** What a live share releases, from the same function the provider's link calls. */
export function useSharePreview(shareId: number, enabled: boolean) {
  return useQuery({
    queryKey: ['shares', shareId, 'preview'],
    queryFn: () => apiGet<SharePreviewOut>(`/shares/${shareId}/preview`),
    enabled,
  })
}

export function useRevokeShare(matterId: number) {
  const invalidate = useInvalidateShares(matterId)
  return useMutation({
    mutationFn: (shareId: number) => send<ShareOut>('POST', `/shares/${shareId}/revoke`),
    onSuccess: invalidate,
  })
}

/** Where a draft will go: a live share, or one the composer has not created yet. */
export type DraftTarget = { shareId: number } | { matterId: number; share: ShareCreate }

/** A draft check with the exact text it ran on, so its offsets are never applied to newer text. */
export type CheckedDraft = { text: string; check: DraftCheckOut }

function checkDraft(target: DraftTarget, text: string): Promise<DraftCheckOut> {
  if ('shareId' in target) {
    const body: DraftCheckIn = { text }
    return send<DraftCheckOut>('POST', `/shares/${target.shareId}/draft-check`, body)
  }
  const body: DraftShareCheckIn = { share: target.share, text }
  return send<DraftCheckOut>('POST', `/matters/${target.matterId}/shares/draft-check`, body)
}

/**
 * Each amount and date in a draft, checked on the server against what the link shows and
 * withholds. The check runs in code, with no model call. Every new text is a request, so
 * pass text that has settled.
 */
export function useDraftCheck(target: DraftTarget, text: string) {
  return useQuery({
    queryKey: ['draft-check', target, text],
    queryFn: async (): Promise<CheckedDraft> => ({ text, check: await checkDraft(target, text) }),
    enabled: text.trim() !== '',
    // Keep the last marks on screen while the next check runs.
    placeholderData: keepPreviousData,
  })
}
