import { useState } from 'react'

type ClientAvatarProps = {
  name: string
  avatarUrl: string | null
}

function initials(name: string): string {
  const words = name.split(/\s+/).filter(Boolean)
  return words
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? '')
    .join('')
}

/** The client's Clio photo, falling back to initials when there is none or it fails to load. */
export function ClientAvatar({ name, avatarUrl }: ClientAvatarProps) {
  const [failed, setFailed] = useState(false)
  const box = 'size-14 shrink-0 rounded-lg border'
  if (avatarUrl && !failed) {
    return <img src={avatarUrl} alt="" className={`${box} object-cover`} onError={() => setFailed(true)} />
  }
  return (
    <div aria-hidden className={`${box} flex items-center justify-center bg-muted text-lg font-semibold text-muted-foreground`}>
      {initials(name)}
    </div>
  )
}
