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

export const WAITING_ON_LABELS: Record<WaitingOn, string> = {
  firm: 'the firm',
  client: 'the client',
  provider: 'a provider',
  insurer: 'the insurer',
  court: 'the court',
  other: 'someone else',
}
