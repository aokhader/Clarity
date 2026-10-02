import type { FactOut, IsoDate } from '@/api/types'

/** Items due within this many days are marked as due soon. */
export const DUE_SOON_DAYS = 7
/** Client contact older than this many days is flagged. */
export const STALE_CONTACT_DAYS = 30

/** The day a task or deadline is due, as written; other facts fall back to their date. */
export function dueDateOf(fact: FactOut): IsoDate | null {
  if (fact.kind === 'task' || fact.kind === 'deadline') {
    return fact.value.due_at?.slice(0, 10) ?? fact.event_date
  }
  return fact.event_date
}
