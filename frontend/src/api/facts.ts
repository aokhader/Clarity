import { skipToken, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'

import { apiGet } from './client'
import type { FactSourceOut } from './types'

const factSourceKey = (factId: number | null) => ['facts', factId, 'source'] as const
const fetchFactSource = (factId: number) => apiGet<FactSourceOut>(`/facts/${factId}/source`)

/** The source behind a fact. Idle while no fact is selected. */
export function useFactSource(factId: number | null) {
  return useQuery({
    queryKey: factSourceKey(factId),
    queryFn: factId === null ? skipToken : () => fetchFactSource(factId),
  })
}

/** Loads sources ahead of time, so stepping to one in the drawer shows it without a wait. */
export function usePrefetchFactSources() {
  const queryClient = useQueryClient()
  return useCallback(
    (factIds: number[]) => {
      for (const factId of factIds) {
        void queryClient.prefetchQuery({ queryKey: factSourceKey(factId), queryFn: () => fetchFactSource(factId) })
      }
    },
    [queryClient],
  )
}
