import { useState } from 'react'

import { initialsOf } from '@/lib/format'
import { cn } from '@/lib/utils'

type ClientAvatarProps = {
  name: string
  avatarUrl: string | null
  className?: string
}

/** The client's Clio photo, falling back to initials when there is none or it fails to load. */
export function ClientAvatar({ name, avatarUrl, className }: ClientAvatarProps) {
  const [failed, setFailed] = useState(false)
  const box = 'size-12 shrink-0 rounded-full border'
  if (avatarUrl && !failed) {
    return <img src={avatarUrl} alt="" className={cn(box, 'object-cover', className)} onError={() => setFailed(true)} />
  }
  return (
    <div
      aria-hidden
      className={cn(box, 'flex items-center justify-center bg-muted font-serif text-lg text-foreground', className)}
    >
      {initialsOf(name)}
    </div>
  )
}
