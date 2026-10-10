import type { FactKind } from '@/api/types'

/** What kind of thing the user pointed at, which picks the questions offered to start with. */
export type StarterKind =
  | 'bill'
  | 'deadline'
  | 'event'
  | 'injury'
  | 'kpi'
  | 'provider'
  | 'call'
  | 'document'
  | 'stage'
  | 'fact'

/**
 * Questions to start from, by the kind of item pointed at, so the user need not know
 * what to ask (D49). They are generic on purpose: the item itself, sent as ids, is what
 * makes the question about this case.
 */
export const STARTERS: Record<StarterKind, readonly string[]> = {
  bill: [
    'What does this bill cover?',
    'Is this bill counted in the medical specials?',
    'Has this bill been paid, reduced or liened?',
  ],
  deadline: [
    'What has to happen before this is due?',
    'Who is handling this, and what is it waiting on?',
    'What happens if this is missed?',
  ],
  event: ['What led up to this?', 'What changed on the case after this?', 'Which records describe this?'],
  injury: [
    'What treatment has this injury had?',
    'Do the records agree about this injury?',
    'Is the client still treating for this?',
  ],
  kpi: ['How is this figure reached?', 'Do any records disagree with this figure?', 'What could change this figure?'],
  provider: [
    'What has this provider billed, and what is still owed?',
    'Which of this provider’s records are on file, and which are missing?',
    'What is the firm waiting on from this provider?',
  ],
  call: ['What was agreed on this call?', 'What follow-ups came out of this call?'],
  document: [
    'What does this record say about the case?',
    'Which facts on the case come from this record?',
    'Does this record disagree with anything else in the file?',
  ],
  stage: ['What moved the case to this stage?', 'What has to happen to reach the next stage?'],
  fact: ['Which records state this?', 'Does anything in the file contradict this?', 'Why does this matter for the case?'],
}

const STARTER_OF_KIND: Record<FactKind, StarterKind> = {
  case_stage: 'stage',
  status_change: 'event',
  injury: 'injury',
  diagnosis: 'injury',
  treatment_visit: 'event',
  medical_bill: 'bill',
  lien: 'bill',
  records_received: 'event',
  record_request: 'deadline',
  coverage: 'fact',
  policy_limit: 'kpi',
  case_value: 'kpi',
  liability: 'fact',
  demand: 'event',
  offer: 'event',
  settlement: 'event',
  expense: 'fact',
  deadline: 'deadline',
  task: 'deadline',
  client_contact: 'event',
  party: 'fact',
  incident: 'event',
  medical_specials: 'kpi',
  economic_damages: 'kpi',
  recovery_cap: 'kpi',
  call_note: 'call',
  litigation_event: 'event',
  other: 'fact',
}

/** The starter questions that suit a fact of this kind. */
export function starterKindOf(kind: FactKind): StarterKind {
  return STARTER_OF_KIND[kind]
}
