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

/** $75,000 – $150,000, or a single amount when only one end is known. */
export function formatMoneyRange(lowCents: number | null, highCents: number | null): string | null {
  if (lowCents !== null && highCents !== null) {
    return lowCents === highCents
      ? formatMoney(lowCents)
      : `${formatMoney(lowCents)} – ${formatMoney(highCents)}`
  }
  const single = lowCents ?? highCents
  return single === null ? null : formatMoney(single)
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

/** 12 days, 7 months, 2 years: the time elapsed since a day. */
export function formatElapsed(iso: IsoDate | IsoDateTime): string {
  const days = Math.max(0, -daysFromToday(iso))
  if (days < 60) return days === 1 ? '1 day' : `${days} days`
  const months = Math.floor(days / 30.44)
  if (months < 24) return `${months} months`
  return `${Math.floor(months / 12)} years`
}
