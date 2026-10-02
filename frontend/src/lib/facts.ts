import type { FactOut, IsoDate } from '@/api/types'
import { formatMonth } from '@/lib/format'

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

export type MonthGroup = {
  key: string
  label: string
  facts: FactOut[]
}

/** Facts grouped by calendar month in the order given, with undated facts as their own group. */
export function groupByMonth(facts: FactOut[]): MonthGroup[] {
  const groups = new Map<string, FactOut[]>()
  for (const fact of facts) {
    const key = fact.event_date?.slice(0, 7) ?? 'undated'
    groups.set(key, [...(groups.get(key) ?? []), fact])
  }
  return [...groups].map(([key, grouped]) => ({
    key,
    label: key === 'undated' ? 'Undated' : formatMonth(key),
    facts: grouped,
  }))
}
