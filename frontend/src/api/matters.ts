import { useQuery } from '@tanstack/react-query'

import { apiGet } from './client'
import type { ActionsOut, FactOut, MatterHeaderOut, MatterSummaryOut } from './types'

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
