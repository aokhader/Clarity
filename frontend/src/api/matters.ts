import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { apiGet } from './client'
import type { ActionsOut, BriefOut, FactKind, FactOut, MatterHeaderOut, MatterSummaryOut } from './types'

export function useMatterBrief(matterId: number) {
  return useQuery({
    queryKey: ['matters', matterId, 'brief'],
    queryFn: () => apiGet<BriefOut>(`/matters/${matterId}/brief`),
  })
}

export function useMatterInjuries(matterId: number) {
  return useQuery({
    queryKey: ['matters', matterId, 'injuries'],
    queryFn: () => apiGet<FactOut[]>(`/matters/${matterId}/injuries`),
  })
}

export function useMatters() {
  return useQuery({
    queryKey: ['matters'],
    queryFn: () => apiGet<MatterSummaryOut[]>('/matters'),
  })
}

export function useMatterHeader(matterId: number) {
  return useQuery({
    queryKey: ['matters', matterId, 'header'],
    queryFn: () => apiGet<MatterHeaderOut>(`/matters/${matterId}`),
  })
}

export function useMatterActions(matterId: number) {
  return useQuery({
    queryKey: ['matters', matterId, 'actions'],
    queryFn: () => apiGet<ActionsOut>(`/matters/${matterId}/actions`),
  })
}

export function useMatterFeed(matterId: number, limit = 10) {
  return useQuery({
    queryKey: ['matters', matterId, 'feed', limit],
    queryFn: () => apiGet<FactOut[]>(`/matters/${matterId}/feed?limit=${limit}`),
  })
}

export function useMatterTimeline(matterId: number, kind: FactKind | null, text: string) {
  const params = new URLSearchParams()
  if (kind) params.set('kind', kind)
  if (text) params.set('q', text)
  const search = params.size > 0 ? `?${params.toString()}` : ''
  return useQuery({
    queryKey: ['matters', matterId, 'timeline', kind, text],
    queryFn: () => apiGet<FactOut[]>(`/matters/${matterId}/timeline${search}`),
    // Keep the last result on screen while a new filter loads, so the list does not flash.
    placeholderData: keepPreviousData,
  })
}
