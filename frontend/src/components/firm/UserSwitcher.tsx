import { useId } from 'react'

import { useFirmUser, useUsers } from '@/api/users'
import { selectFirmUser } from '@/lib/firmUser'

/** Picks the stub firm user the page acts as. There is no real login. */
export function UserSwitcher() {
  const users = useUsers()
  const current = useFirmUser()
  const selectId = useId()
  if (!users.data || current === null) return null
  return (
    <div className="flex items-center gap-2 text-sm">
      <label htmlFor={selectId} className="whitespace-nowrap text-muted-foreground">
        Viewing as
      </label>
      <select
        id={selectId}
        value={current.id}
        onChange={(event) => selectFirmUser(Number(event.target.value))}
        className="h-8 rounded-md border bg-card px-2 text-sm focus-visible:outline-2 focus-visible:outline-ring"
      >
        {users.data.map((user) => (
          <option key={user.id} value={user.id}>
            {user.name} ({user.role})
          </option>
        ))}
      </select>
    </div>
  )
}
