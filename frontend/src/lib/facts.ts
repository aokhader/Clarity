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

/** The `count` facts the file weighs most, heaviest first; equals keep the order given. */
export function topBySignificance<F extends FactOut>(facts: F[] | undefined, count: number): F[] {
  return [...(facts ?? [])].sort((a, b) => b.significance - a.significance).slice(0, count)
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

/** Words that say which side, not which part: a left and a right knee are one region. */
const SIDE_WORDS = /\b(left|right|bilateral|both|lt|rt|l|r)\b/g

/** A body part as a region: lower case, with side words and punctuation dropped; empty when none is given. */
export function bodyRegionOf(bodyPart: string | null | undefined): string {
  return (bodyPart ?? '')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s-]/gu, ' ')
    .replace(SIDE_WORDS, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

/** How many distinct source records state these facts. */
function recordsStating(facts: Injury[]): number {
  return new Set(facts.map((fact) => fact.source_id)).size
}

/** The first fact from each source record, in the order given. */
function onePerRecord(facts: Injury[]): Injury[] {
  const seen = new Set<number>()
  return facts.filter((fact) => {
    if (seen.has(fact.source_id)) return false
    seen.add(fact.source_id)
    return true
  })
}

/** One body region as the Overview shows it. */
export type RegionGroup = {
  /** The region as normalized; empty for injuries the records give no body part for. */
  region: string
  /** The region's leading finding, stated by the most records (groupInjuriesByRegion). */
  lead: Injury
  /** That finding's facts, one per record, the lead first. */
  facts: Injury[]
  /** How many distinct records state an injury in the region: the order of the list. */
  recordCount: number
}

/**
 * Injuries by body region, the region the most records state first, ties in the order
 * given, and injuries with no body part last. Every chart visit restates its complaint,
 * so counting records rather than facts keeps one busy chart from leading the list.
 *
 * A region's row is chosen as the incident account is (D39): its facts are grouped by
 * finding (groupSameInjuries), and the finding the most records state leads, ties going
 * to the order served, which puts treating providers first. Significance alone would
 * pick a single negative or defense finding over what the treating records say (D40).
 */
export function groupInjuriesByRegion(injuries: Injury[]): RegionGroup[] {
  const byRegion = new Map<string, Injury[]>()
  for (const fact of injuries) {
    const region = bodyRegionOf(fact.value.body_part)
    byRegion.set(region, [...(byRegion.get(region) ?? []), fact])
  }
  const groups: RegionGroup[] = []
  for (const [region, facts] of byRegion) {
    // groupSameInjuries keeps the served order; a stable sort keeps it among equal counts.
    const findings = groupSameInjuries(facts).sort((a, b) => recordsStating(b.facts) - recordsStating(a.facts))
    const [leading] = findings
    if (leading === undefined) continue
    groups.push({
      region,
      lead: leading.lead,
      facts: onePerRecord(leading.facts),
      recordCount: recordsStating(facts),
    })
  }
  return groups.sort((a, b) => {
    if ((a.region === '') !== (b.region === '')) return a.region === '' ? 1 : -1
    return b.recordCount - a.recordCount
  })
}
