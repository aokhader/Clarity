import { skipToken, useMutation, useQuery } from '@tanstack/react-query'

import { apiGet, apiPost } from './client'
import type { ChangesOut, OpenedOut } from './types'

export function useMatterChanges(matterId: number, userId: number | null) {
  return useQuery({
    queryKey: ['matters', matterId, 'changes', userId],
    queryFn:
      userId === null ? skipToken : () => apiGet<ChangesOut>(`/matters/${matterId}/changes`, { userId }),
    // Fetched once per visit: recording the visit straight after must not empty the
    // list the user is reading.
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  })
}

export function useRecordVisit(matterId: number) {
  return useMutation({
    mutationFn: (userId: number) => apiPost<OpenedOut>(`/matters/${matterId}/opened`, { userId }),
  })
}
