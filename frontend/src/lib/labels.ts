import type { CaseStage, FactKind, SourceType, WaitingOn } from '@/api/types'

export const KIND_LABELS: Record<FactKind, string> = {
  case_stage: 'Stage',
  status_change: 'Status',
  injury: 'Injury',
  diagnosis: 'Diagnosis',
  treatment_visit: 'Treatment',
  medical_bill: 'Bill',
  lien: 'Lien',
  records_received: 'Records',
  record_request: 'Request',
  coverage: 'Coverage',
  policy_limit: 'Policy limit',
  case_value: 'Value',
  liability: 'Liability',
  demand: 'Demand',
  offer: 'Offer',
  settlement: 'Settlement',
  expense: 'Expense',
  deadline: 'Deadline',
  task: 'Task',
  client_contact: 'Client contact',
  party: 'Party',
  incident: 'Incident',
  medical_specials: 'Specials',
  economic_damages: 'Economic damages',
  recovery_cap: 'Recovery cap',
  call_note: 'Call note',
  other: 'Other',
}

export const SOURCE_LABELS: Record<SourceType, string> = {
  matter: 'Matter',
  custom_field: 'Field',
  contact: 'Contact',
  relationship: 'Contact',
  note: 'Note',
  communication: 'Email',
  task: 'Task',
  calendar_entry: 'Calendar',
  activity: 'Expense',
  document: 'Doc',
  call: 'Call',
}

export const STAGE_LABELS: Record<CaseStage, string> = {
  intake: 'Intake',
  treating: 'Treating',
  treatment_complete: 'Treatment complete',
  demand: 'Demand',
  negotiation: 'Negotiation',
  litigation: 'Litigation',
  settled: 'Settled',
  closed: 'Closed',
}

/** The stage track's five steps, in order; each is named by its STAGE_LABELS entry. */
export const STAGE_STEPS = ['intake', 'treating', 'demand', 'negotiation', 'litigation'] as const satisfies readonly CaseStage[]

/**
 * Where each stage sits on the track, from 1 to STAGE_STEPS.length. A finished treatment
 * is still the treating step. Settled and closed are past the last step: the whole
 * track is done, and they are named by their own label, not by a step number.
 */
export const STEP_OF_STAGE: Record<CaseStage, number | 'past_end'> = {
  intake: 1,
  treating: 2,
  treatment_complete: 2,
  demand: 3,
  negotiation: 4,
  litigation: 5,
  settled: 'past_end',
  closed: 'past_end',
}

/** The three lanes a key event belongs to; the word carries the meaning, the dot only echoes it. */
export type Lane = 'case' | 'treatment' | 'negotiation'

export const LANE_LABELS: Record<Lane, string> = {
  case: 'Case',
  treatment: 'Treatment',
  negotiation: 'Negotiation',
}

const KIND_LANE: Partial<Record<FactKind, Lane>> = {
  incident: 'case',
  status_change: 'case',
  coverage: 'case',
  deadline: 'case',
  records_received: 'case',
  diagnosis: 'treatment',
  treatment_visit: 'treatment',
  demand: 'negotiation',
  offer: 'negotiation',
  settlement: 'negotiation',
}

/** A fact's lane on the story so far; a kind with no lane of its own is the case's. */
export function laneOf(kind: FactKind): Lane {
  return KIND_LANE[kind] ?? 'case'
}

export const WAITING_ON_LABELS: Record<WaitingOn, string> = {
  firm: 'the firm',
  client: 'the client',
  provider: 'a provider',
  insurer: 'the insurer',
  court: 'the court',
  other: 'someone else',
}
