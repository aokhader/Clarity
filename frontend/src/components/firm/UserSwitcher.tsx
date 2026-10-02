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
    <div className="border-t border-slate-800 px-6 py-4">
      <div className="flex items-center gap-3">
        <span
          aria-hidden
          className="flex size-8 items-center justify-center rounded-full bg-slate-700 text-[11px] font-bold"
        >
          {initialsOf(current.name)}
        </span>
        <div className="min-w-0">
          <p className="truncate text-[13px] font-semibold">{current.name}</p>
          <p className="truncate text-xs capitalize text-slate-400">{current.role}</p>
        </div>
      </div>
      <label htmlFor={selectId} className="mt-3 block text-[11px] font-semibold tracking-[0.08em] text-slate-400">
        VIEWING AS
      </label>
      <select
        id={selectId}
        value={current.id}
        onChange={(event) => selectFirmUser(Number(event.target.value))}
        className="mt-1 h-8 w-full rounded-md border border-slate-700 bg-slate-800 px-2 text-sm text-slate-100 focus-visible:outline-2 focus-visible:outline-ring"
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
