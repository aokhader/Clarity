import type { ProviderItemOut, ProviderPayload } from '@/api/types'
import { formatDate, formatMoney, formatMonth } from '@/lib/format'
import { STAGE_LABELS } from '@/lib/labels'

/** Recent updates quoted in a message; the link has the full list. */
const UPDATES_IN_MESSAGE = 3

export type ProviderUpdateMessage = {
  subject: string
  /** The full update, for email or the clipboard. */
  body: string
  /** Status, coverage, and open requests only, for a text message. */
  short: string
}

function plural(n: number, noun: string): string {
  return `${n} ${noun}${n === 1 ? '' : 's'}`
}

function itemLine(item: ProviderItemOut): string {
  const on = item.on ? `${formatDate(item.on)}: ` : ''
  const money = item.amount_cents === null ? null : formatMoney(item.amount_cents)
  // A bill's label often already states its amount; say it once.
  const amount = money === null || item.label.includes(money) ? '' : ` (${money})`
  return `- ${on}${item.label}${amount}`
}

function totalCents(items: ProviderItemOut[]): number {
  return items.reduce((sum, item) => sum + (item.amount_cents ?? 0), 0)
}

/**
 * A plain-text update for a provider's office, written from the share's payload and
 * nothing else. A section the attorney turned off is null in the payload and is left
 * out here, so the message can never say more than the provider's link does.
 */
export function providerUpdateText(payload: ProviderPayload, url: string): ProviderUpdateMessage {
  const { status, coverage, requests, bills, records, treatment_activity, updates, note } = payload
  const sections: string[][] = []
  const shortLines: string[] = []

  if (status) {
    const stage = status.current ? STAGE_LABELS[status.current] : 'Not recorded yet'
    const line = `Case status: ${stage}, ${status.active ? 'active' : 'closed'}`
    const lines = [status.last_movement_on ? `${line} (last movement ${formatDate(status.last_movement_on)})` : line]
    if (updates && updates.length > 0) {
      lines.push('Recent updates:')
      lines.push(
        ...updates.slice(-UPDATES_IN_MESSAGE).map((update) => `- ${update.on ? `${formatDate(update.on)}: ` : ''}${update.label}`),
      )
    }
    sections.push(lines)
    shortLines.push(line)
  }

  if (coverage) {
    const lines: string[] = []
    if (coverage.confirmed !== null) {
      const line = `Insurance coverage: ${coverage.confirmed ? 'confirmed' : 'not yet confirmed'}`
      lines.push(line)
      shortLines.push(line)
    }
    if (coverage.limits && coverage.limits.length > 0) lines.push('Policy limits:', ...coverage.limits.map(itemLine))
    if (lines.length > 0) sections.push(lines)
  }

  if (requests) {
    sections.push(
      requests.length === 0
        ? ['Nothing outstanding from your office.']
        : ['What the firm needs from your office:', ...requests.map(itemLine)],
    )
    shortLines.push(
      requests.length === 0 ? 'Nothing needed from your office.' : `The firm needs ${plural(requests.length, 'item')} from your office.`,
    )
  }

  if (bills) {
    sections.push(
      bills.length === 0
        ? ['No bills from your office on file.']
        : [`Your bills on file: ${plural(bills.length, 'bill')}, ${formatMoney(totalCents(bills))} in total`, ...bills.map(itemLine)],
    )
  }

  if (records) {
    sections.push(
      records.length === 0
        ? ['No records from your office on file.']
        : [`Your records on file: ${plural(records.length, 'record')}`, ...records.map(itemLine)],
    )
  }

  if (treatment_activity) {
    sections.push([`Most recent treatment visit on file: ${formatMonth(treatment_activity.last_visit_month)}`])
  }

  if (note) sections.push(['Note from the firm:', note])

  const expiry = payload.expires_on ? ` The link stops working after ${formatDate(payload.expires_on)}.` : ''
  const patient = payload.patient_name ? ` for ${payload.patient_name}` : ''
  const body = [
    `Hello ${payload.provider_name},`,
    `Here is where the case${patient} stands.`,
    ...sections.map((lines) => lines.join('\n')),
    `See the full status and your documents: ${url}${expiry}`,
  ].join('\n\n')

  return {
    subject: `Case update${patient}`,
    body,
    short: [`Case update${patient}.`, ...shortLines, url].join('\n'),
  }
}
