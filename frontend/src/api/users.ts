import { useQuery } from '@tanstack/react-query'

import { apiGet } from './client'
import type { UserOut } from './types'

export function useUsers() {
  return useQuery({
    queryKey: ['users'],
    queryFn: () => apiGet<UserOut[]>('/users'),
    staleTime: Infinity,
  })
}

/**
 * The firm user the page acts as: the first seeded stub user. There is no login and no
 * switcher (D48); the user still dates "since you last opened", logs who placed a call and
 * who made a provider link.
 */
export function useFirmUser(): UserOut | null {
  const users = useUsers()
  return users.data?.[0] ?? null
}
