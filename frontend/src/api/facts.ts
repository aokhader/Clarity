import { skipToken, useQuery } from '@tanstack/react-query'

import { apiGet } from './client'
import type { FactSourceOut } from './types'

/** The source behind a fact. Idle while no fact is selected. */
export function useFactSource(factId: number | null) {
  return useQuery({
    queryKey: ['facts', factId, 'source'],
    queryFn: factId === null ? skipToken : () => apiGet<FactSourceOut>(`/facts/${factId}/source`),
  })
}
