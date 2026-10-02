import { useQuery } from '@tanstack/react-query'

import { apiGet } from './client'
import type { HealthOut } from './types'

export function useHealth() {
  return useQuery({
    queryKey: ['ops', 'health'],
    queryFn: () => apiGet<HealthOut>('/ops/health'),
  })
}
