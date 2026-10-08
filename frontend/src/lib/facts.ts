import type { ActionsOut, FactOf, FactOut, IsoDate } from '@/api/types'
import { daysFromToday, formatMonth } from '@/lib/format'

/** Items due within this many days are marked as due soon. */
export const DUE_SOON_DAYS = 7
/** Client contact older than this many days is flagged. */
export const STALE_CONTACT_DAYS = 30
/** A statute of limitations within this many days is marked as near. */
export const STATUTE_SOON_DAYS = 90

/** The day a task or deadline is due, as written; other facts fall back to their date. */
export function dueDateOf(fact: FactOut): IsoDate | null {
  if (fact.kind === 'task' || fact.kind === 'deadline') {
    return fact.value.due_at?.slice(0, 10) ?? fact.event_date
  }
  return fact.event_date
}

/** The day an open action is due. A record request's date is when it was sent, not when it is due. */
export function actionDueDate(fact: FactOut): IsoDate | null {
  return fact.kind === 'record_request' ? null : dueDateOf(fact)
}

/** Who an open action is assigned to; only tasks carry an assignee. */
export function actionOwner(fact: FactOut): string | null {
  return fact.kind === 'task' ? fact.value.assignee : null
}

/** Red once past due, amber when due within DUE_SOON_DAYS, muted otherwise. */
export function dueTone(days: number): string {
  if (days < 0) return 'text-danger'
  if (days <= DUE_SOON_DAYS) return 'text-warning'
  return 'text-muted-foreground'
}

/** The fact the file weighs most, the first of equals; null for none. */
export function mostSignificant(facts: FactOut[] | undefined): FactOut | null {
  if (!facts || facts.length === 0) return null
  return facts.reduce((best, fact) => (fact.significance > best.significance ? fact : best))
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

export function isStatuteDeadline(fact: FactOut): fact is FactOf<'deadline'> {
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

/**
 * What the firm should do next: the first overdue item, else the first task coming up,
 * else the first deadline coming up that is not the statute (which has its own cell).
 */
export function nextStep(actions: ActionsOut): { fact: FactOut; overdue: boolean } | null {
  const [overdue] = actions.overdue
  if (overdue) return { fact: overdue, overdue: true }
  const upcoming =
    actions.upcoming.find((fact) => fact.kind === 'task') ??
    actions.upcoming.find((fact) => fact.kind === 'deadline' && !isStatuteDeadline(fact))
  return upcoming ? { fact: upcoming, overdue: false } : null
}

export type Injury = FactOf<'injury' | 'diagnosis'>

export function isInjury(fact: FactOut): fact is Injury {
  return fact.kind === 'injury' || fact.kind === 'diagnosis'
}

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
