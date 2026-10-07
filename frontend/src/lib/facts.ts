import type { FactOf, FactOut, IsoDate } from '@/api/types'
import { daysFromToday, formatMonth } from '@/lib/format'

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

function isStatuteDeadline(fact: FactOut): fact is FactOf<'deadline'> {
  return fact.kind === 'deadline' && /statute.of.limitation/i.test(fact.value.deadline_type ?? fact.title)
}

/**
 * The statute of limitations among a matter's deadlines: the next one still ahead, or
 * the latest one already passed when none is ahead.
 */
export function statuteDeadline(facts: FactOut[]): { fact: FactOf<'deadline'>; due: IsoDate } | null {
  const dated = facts
    .filter(isStatuteDeadline)
    .map((fact) => ({ fact, due: dueDateOf(fact) }))
    .filter((entry): entry is { fact: FactOf<'deadline'>; due: IsoDate } => entry.due !== null)
    .sort((a, b) => a.due.localeCompare(b.due))
  return dated.find((entry) => daysFromToday(entry.due) >= 0) ?? dated.at(-1) ?? null
}

export type Injury = FactOf<'injury' | 'diagnosis'>

/** One injury as the list shows it, with every fact that states it, the first leading. */
export type InjuryGroup = {
  key: string
  lead: Injury
  facts: Injury[]
}

/**
 * Injuries that read the same (kind, title, body part, severity), in the order given.
 * A chart restates an injury on every visit page; this shows it once, citing each page.
 */
export function groupSameInjuries(injuries: Injury[]): InjuryGroup[] {
  const groups = new Map<string, InjuryGroup>()
  for (const fact of injuries) {
    const { body_part: bodyPart, severity } = fact.value
    const key = [fact.kind, fact.title, bodyPart, severity]
      .map((part) => (part ?? '').trim().toLowerCase().replace(/\s+/g, ' '))
      .join('|')
    const group = groups.get(key)
    if (group) group.facts.push(fact)
    else groups.set(key, { key, lead: fact, facts: [fact] })
  }
  return [...groups.values()]
}
