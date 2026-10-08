import { useId } from 'react'

import { useFirmUser, useUsers } from '@/api/users'
import { selectFirmUser } from '@/lib/firmUser'
import { initialsOf } from '@/lib/format'

/** The stub firm user the page acts as, at the foot of the sidebar. There is no real login. */
export function UserSwitcher() {
  const users = useUsers()
  const current = useFirmUser()
  const selectId = useId()
  if (!users.data || current === null) return null
  return (
    <div className="border-t px-5 py-4">
      <div className="flex items-center gap-3">
        <span
          aria-hidden
          className="flex size-8 items-center justify-center rounded-full border bg-muted text-[11px] font-semibold text-foreground"
        >
          {initialsOf(current.name)}
        </span>
        <div className="min-w-0">
          <p className="truncate text-[13px] font-medium">{current.name}</p>
          <p className="truncate text-xs capitalize text-muted-foreground">{current.role}</p>
        </div>
      </div>
      <label
        htmlFor={selectId}
        className="mt-3 block text-[11px] font-medium tracking-[0.08em] text-muted-foreground uppercase"
      >
        Viewing as
      </label>
      <select
        id={selectId}
        value={current.id}
        onChange={(event) => selectFirmUser(Number(event.target.value))}
        className="mt-1 h-8 w-full rounded-md border border-input bg-card px-2 text-sm text-foreground"
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
