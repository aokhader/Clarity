import { useQuery } from '@tanstack/react-query'

import { useSelectedFirmUserId } from '@/lib/firmUser'

import { apiGet } from './client'
import type { UserOut } from './types'

export function useUsers() {
  return useQuery({
    queryKey: ['users'],
    queryFn: () => apiGet<UserOut[]>('/users'),
    staleTime: Infinity,
  })
}

/** The firm user chosen in the switcher, or the first stub user until one is chosen. */
export function useFirmUser(): UserOut | null {
  const users = useUsers()
  const selectedId = useSelectedFirmUserId()
  const all = users.data ?? []
  return all.find((user) => user.id === selectedId) ?? all[0] ?? null
}
