import type { ShareStatusOut } from '@/api/types'
import { formatDate, formatDateTime } from '@/lib/format'
import { cn } from '@/lib/utils'

type ShareStatusProps = {
  share: ShareStatusOut | null
  /** When the panel loaded, so an expired link reads as expired. */
  now: Date
}

/** Not shared, shared but unopened, opened (with when), withdrawn, or expired. */
export function ShareStatus({ share, now }: ShareStatusProps) {
  let text: string
  let tone = 'text-muted-foreground'
  if (share === null) {
    text = 'Not shared'
  } else if (share.revoked) {
    text = 'Link withdrawn'
  } else if (share.expires_at !== null && new Date(share.expires_at) <= now) {
    text = `Link expired ${formatDate(share.expires_at)}`
  } else if (share.last_opened_at !== null) {
    const times = share.opened_count === 1 ? 'once' : `${share.opened_count} times`
    text = `Opened ${formatDateTime(share.last_opened_at)} (${times})`
    tone = 'text-success'
  } else {
    text = `Shared ${formatDate(share.created_at)}, not opened yet`
    tone = 'text-foreground'
  }
  return <span className={cn('tabular-nums', tone)}>{text}</span>
}
