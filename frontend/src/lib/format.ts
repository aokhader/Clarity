// Every amount and date on screen is formatted here, so they read the same everywhere.

import type { IsoDate, IsoDateTime } from '@/api/types'

const wholeDollars = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
})
const dollarsAndCents = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })

/** $2,480 for whole dollars, $2,480.50 otherwise. */
export function formatMoney(cents: number): string {
  return (cents % 100 === 0 ? wholeDollars : dollarsAndCents).format(cents / 100)
}

/**
 * A two-ended range as its ends, the dash kept with the first: "$75,000 –" and "$150,000".
 * A figure too wide for its box breaks between them, never inside an amount.
 */
export function formatMoneyRangeEnds(lowCents: number, highCents: number): string[] {
  return lowCents === highCents ? [formatMoney(lowCents)] : [`${formatMoney(lowCents)} –`, formatMoney(highCents)]
}

/** $75,000 – $150,000; "at least $75,000" or "up to $150,000" when only one end is known. */
export function formatMoneyRange(lowCents: number | null, highCents: number | null): string | null {
  if (lowCents !== null && highCents !== null) return formatMoneyRangeEnds(lowCents, highCents).join(' ')
  if (lowCents !== null) return `at least ${formatMoney(lowCents)}`
  if (highCents !== null) return `up to ${formatMoney(highCents)}`
  return null
}

/**
 * Read the calendar day of an ISO date or datetime as written. `new Date('2026-03-06')`
 * would be UTC midnight and show March 5 in California.
 */
export function calendarDay(iso: IsoDate | IsoDateTime): Date {
  const [year, month, day] = iso.slice(0, 10).split('-').map(Number)
  return new Date(year, month - 1, day)
}

const dateFormat = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
const timeFormat = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
})

/** Mar 6, 2026 */
export function formatDate(iso: IsoDate | IsoDateTime): string {
  return dateFormat.format(calendarDay(iso))
}

/** Oct 2, 10:42 AM, in the viewer's time zone. */
export function formatDateTime(iso: IsoDateTime): string {
  return timeFormat.format(new Date(iso))
}

const monthFormat = new Intl.DateTimeFormat('en-US', { month: 'long', year: 'numeric' })

/** 2026-03 -> March 2026 */
export function formatMonth(yearMonth: string): string {
  return monthFormat.format(calendarDay(`${yearMonth}-01`))
}

const MS_PER_DAY = 86_400_000

/** Whole calendar days from today to the given day: negative in the past. */
export function daysFromToday(iso: IsoDate | IsoDateTime, today: Date = new Date()): number {
  const day = calendarDay(iso)
  const utcDay = Date.UTC(day.getFullYear(), day.getMonth(), day.getDate())
  const utcToday = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate())
  return Math.round((utcDay - utcToday) / MS_PER_DAY)
}

/** today, yesterday, 12 days ago */
export function formatDaysAgo(iso: IsoDate | IsoDateTime): string {
  const days = -daysFromToday(iso)
  if (days <= 0) return 'today'
  if (days === 1) return 'yesterday'
  return `${days} days ago`
}

/** 3 days overdue, due today, tomorrow, in 5 days: when an action falls due, from whole days ahead. */
export function formatDueIn(days: number): string {
  if (days < -1) return `${-days} days overdue`
  if (days === -1) return '1 day overdue'
  if (days === 0) return 'due today'
  if (days === 1) return 'tomorrow'
  return `in ${days} days`
}

/** today, in 40 days, passed 3 days ago: a deadline's countdown, from whole days ahead. */
export function formatDaysUntil(days: number): string {
  if (days === 0) return 'today'
  if (days > 0) return `in ${days} day${days === 1 ? '' : 's'}`
  return `passed ${-days} day${days === -1 ? '' : 's'} ago`
}

/** 1 record, 3 records: a count with its noun, plural unless it is one. */
export function formatCount(n: number, noun: string): string {
  return `${n} ${noun}${n === 1 ? '' : 's'}`
}

/** 12 days, 7 months, 2 years: the time elapsed since a day. */
export function formatElapsed(iso: IsoDate | IsoDateTime): string {
  const days = Math.max(0, -daysFromToday(iso))
  if (days < 60) return days === 1 ? '1 day' : `${days} days`
  const months = Math.floor(days / 30.44)
  if (months < 24) return `${months} months`
  return `${Math.floor(months / 12)} years`
}

/** Model spend, stored as integer micro-dollars: $0.42, or "under $0.01" for a sliver. */
export function formatMicroDollars(micros: number): string {
  if (micros === 0) return '$0.00'
  if (micros < 10_000) return 'under $0.01'
  return dollarsAndCents.format(micros / 1_000_000)
}

/** Up to two initials for an avatar, from the first two words of a name. */
export function initialsOf(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? '')
    .join('')
}
