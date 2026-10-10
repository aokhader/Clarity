import type { KpiOut, KpiValueOut } from '@/api/types'

/** A value's low and high ends; a single amount is both. */
function endsOf(value: KpiValueOut): [number | null, number | null] {
  return [value.amount_cents ?? value.low_cents, value.amount_cents ?? value.high_cents]
}

/**
 * Whether `value` states nothing the lead does not: the same label, and each end it
 * gives is the lead's own end. "At least $X" under a lead of $X is the lead once more.
 */
function restatesLead(value: KpiValueOut, lead: KpiValueOut): boolean {
  if (value.label !== lead.label) return false
  const [low, high] = endsOf(value)
  const [leadLow, leadHigh] = endsOf(lead)
  if (low === null && high === null) return false
  return (low === null || low === leadLow) && (high === null || high === leadHigh)
}

/**
 * A tile's lead and the entries listed under it, with each entry that restates the lead
 * folded into it: its facts join the lead's chips instead of repeating the figure.
 * Coverage is left as served, since its entries are different policies (D37).
 */
export function foldIntoLead(
  kpi: KpiOut['name'],
  lead: KpiValueOut,
  others: KpiValueOut[],
): { lead: KpiValueOut; others: KpiValueOut[] } {
  if (kpi === 'coverage') return { lead, others }
  const restating = others.filter((value) => restatesLead(value, lead))
  if (restating.length === 0) return { lead, others }
  const cited = new Set(lead.facts.map((fact) => fact.id))
  const facts = [...lead.facts]
  for (const fact of restating.flatMap((value) => value.facts)) {
    if (!cited.has(fact.id)) facts.push(fact)
    cited.add(fact.id)
  }
  return { lead: { ...lead, facts }, others: others.filter((value) => !restatesLead(value, lead)) }
}
