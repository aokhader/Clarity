// Mirrors backend/app/schemas.py and the enums it uses from backend/app/models.py.
// Frozen after M0: change both sides in one commit (docs/parallel.md).
// Stored-only shapes (BriefContent, FieldMappingContent) never cross the API and are not mirrored.

/** ISO 8601 date, e.g. 2026-10-02. */
export type IsoDate = string
/** ISO 8601 datetime with offset. */
export type IsoDateTime = string

// --- Enums -------------------------------------------------------------------------

export type SourceType =
  | 'matter'
  | 'custom_field'
  | 'contact'
  | 'relationship'
  | 'note'
  | 'communication'
  | 'task'
  | 'calendar_entry'
  | 'activity'
  | 'document'
  /** Not a Clio record: a call placed from Clarity, whose transcript its notes cite. */
  | 'call'

export type FactKind =
  | 'case_stage'
  | 'status_change'
  | 'injury'
  | 'diagnosis'
  | 'treatment_visit'
  | 'medical_bill'
  | 'lien'
  | 'records_received'
  | 'record_request'
  | 'coverage'
  | 'policy_limit'
  | 'case_value'
  | 'liability'
  | 'demand'
  | 'offer'
  | 'settlement'
  | 'expense'
  | 'deadline'
  | 'task'
  | 'client_contact'
  | 'party'
  | 'incident'
  | 'medical_specials'
  | 'economic_damages'
  | 'recovery_cap'
  /** A note from a call's transcript. Internal by default-deny. */
  | 'call_note'
  /** D41: something that happened in the lawsuit, dated by when it happened. Internal. */
  | 'litigation_event'
  | 'other'

export type Visibility = 'internal' | 'shareable'
export type Confidence = 'high' | 'medium' | 'low'
export type Origin = 'code' | 'model'

/** Canonical stages, in the order the provider tracker shows them. */
export const CASE_STAGES = [
  'intake',
  'treating',
  'treatment_complete',
  'demand',
  'negotiation',
  'litigation',
  'settled',
  'closed',
] as const
export type CaseStage = (typeof CASE_STAGES)[number]

export type WaitingOn = 'firm' | 'client' | 'provider' | 'insurer' | 'court' | 'other'

// --- Fact payloads (FactOut.value) --------------------------------------------------

export type AltValue = {
  amount_cents: number | null
  on: IsoDate | null
  source_id: number | null
  page_no: number | null
}

type PayloadBase = {
  alt_values: AltValue[]
  corroborating_source_ids: number[]
}

export type CaseStagePayload = PayloadBase & { stage: CaseStage | null; inferred: boolean }
export type StatusChangePayload = PayloadBase & {
  from_stage: CaseStage | null
  to_stage: CaseStage | null
  /** The record's wording, for the firm; a provider never sees it (D41). */
  label: string
}
export type InjuryPayload = PayloadBase & {
  body_part: string | null
  description: string | null
  severity: string | null
}
export type TreatmentVisitPayload = PayloadBase & { visit_type: string | null }
export type BillPayload = PayloadBase & { amount_cents: number | null; balance_cents: number | null }
export type RecordsReceivedPayload = PayloadBase & { description: string | null; page_count: number | null }
export type RecordRequestPayload = PayloadBase & { description: string | null; status: 'open' | 'fulfilled' }
export type CoveragePayload = PayloadBase & {
  carrier: string | null
  coverage_type: string | null
  confirmed: boolean | null
}
/** D19, D21: whose policy a limit belongs to. null is unknown, as on facts read before. */
export type PolicyHolder = 'defendant_liability' | 'client_no_fault' | 'client_um_uim' | 'client_other'
export type PolicyLimitPayload = PayloadBase & {
  amount_cents: number | null
  per: 'person' | 'occurrence' | null
  policy: PolicyHolder | null
}
export type CaseValuePayload = PayloadBase & {
  low_cents: number | null
  high_cents: number | null
  basis: string | null
}
export type LiabilityPayload = PayloadBase & { assessment: string | null }
export type NegotiationPayload = PayloadBase & { amount_cents: number | null; party: string | null }
export type ExpensePayload = PayloadBase & {
  amount_cents: number | null
  category: string | null
  vendor: string | null
}
export type DeadlinePayload = PayloadBase & {
  deadline_type: string | null
  due_at: IsoDateTime | null
  /**
   * The status of the Clio task the deadline was read from, filled when served; null for
   * any other deadline. A statute whose task is complete has been met.
   */
  status: 'open' | 'complete' | null
}
export type TaskPayload = PayloadBase & {
  status: 'open' | 'complete'
  due_at: IsoDateTime | null
  assignee: string | null
  waiting_on: WaitingOn | null
}
export type ClientContactPayload = PayloadBase & {
  channel: 'email' | 'phone' | 'text' | 'meeting' | 'letter' | 'other' | null
  direction: 'inbound' | 'outbound' | null
}
export type PartyPayload = PayloadBase & { role: string | null }
export type IncidentPayload = PayloadBase & { description: string | null }
export type MedicalSpecialsPayload = PayloadBase & { amount_cents: number | null }
/** Specials plus other losses. `basis` says what the total includes. */
export type EconomicDamagesPayload = PayloadBase & { amount_cents: number | null; basis: string | null }
/** A ceiling on what the case can recover. `basis` says what sets it. */
export type RecoveryCapPayload = PayloadBase & { amount_cents: number | null; basis: string | null }
export type CallNoteKind = 'summary' | 'commitment' | 'date' | 'amount' | 'follow_up'
/** A note from a call. The quote is `transcript.slice(quote_start, quote_end)`. */
export type CallNotePayload = PayloadBase & {
  note_kind: CallNoteKind | null
  quote_start: number | null
  quote_end: number | null
  amounts_cents: number[]
  dates: { on: IsoDate; precision: 'day' | 'month' }[]
}
export type LitigationEventType =
  | 'filed'
  | 'served'
  | 'answered'
  | 'dismissed'
  | 'renewed'
  | 'motion'
  | 'order'
  | 'hearing'
  | 'deposition'
  | 'trial'
  | 'other'
/** A hearing or deposition here is one that took place, not one set. */
export type LitigationEventPayload = PayloadBase & { event: LitigationEventType; detail: string | null }
export type OtherPayload = PayloadBase & { detail: string | null }

/** PAYLOAD_BY_KIND in schemas.py. */
export type FactPayloads = {
  case_stage: CaseStagePayload
  status_change: StatusChangePayload
  injury: InjuryPayload
  diagnosis: InjuryPayload
  treatment_visit: TreatmentVisitPayload
  medical_bill: BillPayload
  lien: BillPayload
  records_received: RecordsReceivedPayload
  record_request: RecordRequestPayload
  coverage: CoveragePayload
  policy_limit: PolicyLimitPayload
  case_value: CaseValuePayload
  liability: LiabilityPayload
  demand: NegotiationPayload
  offer: NegotiationPayload
  settlement: NegotiationPayload
  expense: ExpensePayload
  deadline: DeadlinePayload
  task: TaskPayload
  client_contact: ClientContactPayload
  party: PartyPayload
  incident: IncidentPayload
  medical_specials: MedicalSpecialsPayload
  economic_damages: EconomicDamagesPayload
  recovery_cap: RecoveryCapPayload
  call_note: CallNotePayload
  litigation_event: LitigationEventPayload
  other: OtherPayload
}

// --- Facts and sources -------------------------------------------------------------

/** What a source chip needs to render and to open the drawer. */
export type FactRef = {
  id: number
  source_type: SourceType
  page_no: number | null
  confidence: Confidence
}

type FactBase = {
  id: number
  title: string
  event_date: IsoDate | null
  source_id: number
  source_type: SourceType
  page_no: number | null
  quote: string | null
  provider_contact_id: number | null
  visibility: Visibility
  significance: number
  confidence: Confidence
  verified: boolean
  origin: Origin
  created_at: IsoDateTime
  /**
   * Other facts that state the same thing from other records, one per record, so its
   * length counts records. Filled by the ranked feed and key events, which list each fact
   * once; empty elsewhere.
   */
  restated_by: FactRef[]
}

/** A fact as the firm sees it. Narrowing on `kind` types `value`. */
export type FactOut = { [K in FactKind]: FactBase & { kind: K; value: FactPayloads[K] } }[FactKind]
export type FactOf<K extends FactKind> = Extract<FactOut, { kind: K }>

export type PageRef = {
  page_id: number
  page_no: number
  image_url: string
}

/**
 * A document page in the firm's drawer, with its text layer as the image's text
 * alternative (WCAG 1.1.1). Null for a scan, which has no text layer.
 */
export type FirmPageOut = PageRef & {
  text: string | null
}

/** One labelled value of a structured record. Exactly one of the values is set. */
export type SourceFieldOut = {
  label: string
  value: string | null
  on: IsoDate | null
  amount_cents: number | null
}

/** A titled part of a structured record: labelled fields, free text, or both. */
export type SourceSectionOut = {
  heading: string
  fields: SourceFieldOut[]
  text: string | null
}

export type SourceOut = {
  source_id: number
  source_type: SourceType
  title: string | null
  occurred_on: IsoDate | null
  author: string | null
  text: string | null
  pages: FirmPageOut[]
  /** Matters and tasks, laid out by aspect for reading; empty for every other source. */
  sections: SourceSectionOut[]
  /**
   * A document's own date (its received date in Clio), when known. For a document,
   * `occurred_on` is the day it was uploaded, so show "Uploaded" when this is null.
   */
  document_date: IsoDate | null
}

export type FactSourceOut = {
  fact: FactOut
  source: SourceOut
  corroborating: SourceOut[]
}

// --- Firm view ---------------------------------------------------------------------

export type UserOut = {
  id: number
  name: string
  role: string
}

export type MatterSummaryOut = {
  matter_id: number
  display_number: string | null
  description: string | null
  client_name: string | null
  synced_at: IsoDateTime
}

export type ClientOut = {
  contact_id: number | null
  name: string
  avatar_url: string | null
}

export type StageOut = {
  stage: CaseStage | null
  label: string | null
  inferred: boolean
  facts: FactRef[]
}

export type DatedFactOut = {
  on: IsoDate
  fact: FactRef
}

/** What happened on the incident day: the account most records read on it give. */
export type IncidentAccountOut = {
  /** The title of the account's leading fact. */
  text: string
  /** That fact. */
  fact: FactRef
  /** The other records that give it, one fact each, so its length counts records. */
  restated_by: FactRef[]
}

export type KpiValueOut = {
  amount_cents: number | null
  /** A low end alone means "at least". */
  low_cents: number | null
  /** A high end alone means "up to". */
  high_cents: number | null
  /** What this value is, when one tile lists different kinds ("Per occurrence"). */
  label: string | null
  facts: FactRef[]
}

/** One KPI tile. No values means "Not found in file"; two or more means sources disagree. */
export type KpiOut = {
  name: 'case_value' | 'coverage' | 'medical_specials' | 'firm_spend'
  values: KpiValueOut[]
  basis: string | null
  /**
   * True when two values are figures for the same thing: show "Sources disagree" from this,
   * not from the number of values. The Coverage tile lists different policies as separate,
   * labelled entries, which do not disagree (D19).
   */
  sources_disagree: boolean
}

export type RunOut = {
  id: number
  started_at: IsoDateTime
  finished_at: IsoDateTime | null
  error: string | null
  stats: Record<string, unknown> | null
}

export type MatterHeaderOut = {
  matter_id: number
  display_number: string | null
  description: string | null
  client: ClientOut | null
  responsible_attorney: string | null
  opened_on: IsoDate | null
  stage: StageOut
  incident: DatedFactOut | null
  /**
   * Never the date-of-incident field, whose title is a label (D39). Null when no record
   * read on the incident day names an event.
   */
  incident_account: IncidentAccountOut | null
  last_client_contact: DatedFactOut | null
  kpis: KpiOut[]
  digested: boolean
  last_sync: RunOut | null
  last_digest: RunOut | null
}

export type BriefSentenceOut = {
  text: string
  facts: FactRef[]
  /**
   * D12: the sentence's amounts and dates against today's file. A differs mention carries
   * today's value and the facts that state it. Offsets are within `text`.
   */
  verdict: SentenceVerdict
  mentions: DraftMentionOut[]
}

export type BriefOut = {
  headline: string
  /** D14: the facts the headline cites; empty for a brief stored before D14. */
  headline_facts: FactRef[]
  headline_verdict: SentenceVerdict
  headline_mentions: DraftMentionOut[]
  stage: CaseStage
  stage_facts: FactRef[]
  sentences: BriefSentenceOut[]
  open_questions: string[]
  generated_at: IsoDateTime
}

export type ChangesOut = {
  last_opened_at: IsoDateTime | null
  facts: FactOut[]
}

export type OpenedOut = {
  last_opened_at: IsoDateTime
}

export type ActionsOut = {
  overdue: FactOut[]
  upcoming: FactOut[]
  waiting_on_others: FactOut[]
}

// --- Shares and the provider view ---------------------------------------------------

export type ShareSetting =
  | 'case_stage'
  | 'coverage_exists'
  | 'coverage_limits'
  | 'own_bills'
  | 'own_records'
  | 'requests'
  | 'treatment_activity'

export type ShareSettings = Record<ShareSetting, boolean>

export type ShareStatusOut = {
  share_id: number
  created_at: IsoDateTime
  expires_at: IsoDateTime | null
  revoked: boolean
  opened_count: number
  last_opened_at: IsoDateTime | null
}

export type ProviderOut = {
  contact_id: number
  name: string
  role_label: string | null
  /** null: no bill with an amount is on file. Never show it as zero (D16). */
  billed_cents: number | null
  records_received: number
  open_requests: number
  share: ShareStatusOut | null
}

export type ShareCreate = {
  provider_contact_id: number
  settings?: ShareSettings
  hidden_fact_ids?: number[]
  note?: string | null
  expires_in_days?: number | null
}

/** PATCH body. Only the fields present are changed. */
export type ShareUpdate = {
  settings?: ShareSettings
  hidden_fact_ids?: number[]
  note?: string | null
  expires_at?: IsoDateTime | null
}

export type ShareOut = {
  id: number
  matter_id: number
  provider_contact_id: number
  provider_name: string
  url: string
  settings: ShareSettings
  hidden_fact_ids: number[]
  note: string | null
  created_by: number
  created_at: IsoDateTime
  expires_at: IsoDateTime | null
  revoked_at: IsoDateTime | null
  opened_count: number
  last_opened_at: IsoDateTime | null
}

/** D35: what an item in the provider's bills and liens is. Null in every other section. */
export type ProviderItemKind = 'bill' | 'lien'

export type ProviderItemOut = {
  fact_id: number
  on: IsoDate | null
  label: string
  amount_cents: number | null
  has_source: boolean
  kind: ProviderItemKind | null
}

/** The provider's own bills added up, each charge counted once. */
export type ProviderBillsTotalOut = {
  amount_cents: number
  bill_count: number
}

export type ProviderStatusOut = {
  stages: CaseStage[]
  current: CaseStage | null
  active: boolean
  last_movement_on: IsoDate | null
}

export type ProviderUpdateOut = {
  on: IsoDate | null
  label: string
}

export type ProviderCoverageOut = {
  confirmed: boolean | null
  limits: ProviderItemOut[] | null
}

export type ProviderTreatmentOut = {
  last_visit_month: string
}

/** Everything a provider receives. A section is null when its setting is off. */
export type ProviderPayload = {
  provider_name: string
  patient_name: string | null
  firm_name: string | null
  shared_on: IsoDate
  expires_on: IsoDate | null
  note: string | null
  status: ProviderStatusOut | null
  updates: ProviderUpdateOut[] | null
  coverage: ProviderCoverageOut | null
  requests: ProviderItemOut[] | null
  bills: ProviderItemOut[] | null
  /** Null when bills are not shared or none carries an amount. */
  bills_total: ProviderBillsTotalOut | null
  records: ProviderItemOut[] | null
  treatment_activity: ProviderTreatmentOut | null
}

export type ShareItemOut = {
  fact_id: number
  setting: ShareSetting
  title: string
  event_date: IsoDate | null
  hidden: boolean
}

export type SharePreviewOut = {
  payload: ProviderPayload
  items: ShareItemOut[]
}

export type ProviderSourceOut = {
  fact_id: number
  title: string
  quote: string | null
  page: PageRef | null
}

// --- Draft checker ---------------------------------------------------------------------

/**
 * supported: the link already shows it. differs: the file has another value for the same
 * subject. not_in_file: nothing in the file states it. do_not_send: only facts this link
 * withholds state it. not_on_link (D37): a date in the file that this link does not
 * carry, of a fact not sensitive enough to lock ("In the file, not on this link").
 */
export type MentionVerdict = 'supported' | 'differs' | 'not_in_file' | 'not_on_link' | 'do_not_send'
/** A sentence takes its worst mention's verdict; with no amount or date it is unchecked. */
export type SentenceVerdict = MentionVerdict | 'unchecked'

/** Text a firm user means to send to a provider: an update, or the share's note. */
export type DraftCheckIn = {
  text: string
}

/** The same, before the link exists: checked against what it would release. */
export type DraftShareCheckIn = {
  share: ShareCreate
  text: string
}

/**
 * One amount or date in checked text (a draft, or a brief sentence). Offsets count UTF-16
 * code units, so `text.slice(start, end)` is the mention.
 * `facts` cites what states the value (supported, do_not_send) or the
 * file's value (differs). A do_not_send mention carries no file value (D17).
 */
export type DraftMentionOut = {
  start: number
  end: number
  text: string
  kind: 'amount' | 'date'
  verdict: MentionVerdict
  reason: string
  facts: FactRef[]
  /** differs only */
  file_amount_cents: number | null
  /** differs only */
  file_date: IsoDate | null
}

/**
 * The `detail` of a 422 from creating or updating a share whose note would disclose what
 * the link withholds (rule 4, D25). `locked` holds the spans, as offsets into the note.
 */
export type NoteLockedOut = {
  message: string
  locked: DraftMentionOut[]
}

export type DraftSentenceOut = {
  start: number
  end: number
  text: string
  verdict: SentenceVerdict
  mentions: DraftMentionOut[]
}

export type DraftCheckOut = {
  /** The worst verdict of any sentence; unchecked when nothing could be checked. */
  verdict: SentenceVerdict
  sentences: DraftSentenceOut[]
}

// --- Calls (docs/calls-contract.md; D8, D15, D22, D23) -------------------------------

export type CallRole = 'client' | 'provider' | 'insurer' | 'other'
export type NotesStatus = 'not_started' | 'running' | 'done' | 'failed' | 'no_model'

export type CallTargetOut = {
  /** "contact:<clio id>" or "entered:<id>" */
  target_id: string
  name: string | null
  role: CallRole
  /** null: no number on file; the UI offers to type one. */
  phone: string | null
  phone_source: 'clio' | 'entered' | null
  /** The open item that makes this call due, in a few words. */
  reason: string | null
  /** That item's source, for its chip. */
  reason_fact: FactRef | null
  /** null means no contact found, never zero. */
  last_contact_days: number | null
  /** The record behind last_contact_days, for its chip (rule 3, D23). */
  last_contact_fact: FactRef | null
}

/** A typed name and number, stored in Clarity only (D15). */
export type CallNumberIn = {
  name: string
  phone: string
}

export type CallStartIn = {
  target_id: string
  /** Must be true; the server answers 422 otherwise. */
  consent_confirmed: boolean
  /** The wording the attorney confirmed. */
  consent_text: string
}

export type CallTranscriptIn = {
  /** The whole transcript so far. */
  text: string
  /** True once the call has ended. */
  final: boolean
}

export type CallOut = {
  call_id: number
  target: CallTargetOut
  started_at: IsoDateTime
  ended_at: IsoDateTime | null
  consent_text: string
  notes_status: NotesStatus
}

export type CallNoteOut = {
  /** The stored fact; its source is the transcript. */
  fact: FactRef
  kind: CallNoteKind
  text: string
  /** Offsets into the transcript. */
  quote_start: number
  quote_end: number
}

export type CallDetailOut = {
  call: CallOut
  transcript: string
  notes: CallNoteOut[]
}

// --- Chat (docs/chat-contract.md; D49) -------------------------------------------------

/** An item the user pointed at. The client sends ids only; the server resolves and labels it. */
export type AskItemRef =
  | { kind: 'facts'; fact_ids: number[] }
  | { kind: 'source'; source_id: number }
  /** The Clio contact id, as ProviderOut.contact_id. */
  | { kind: 'provider'; contact_id: number }
  | { kind: 'call'; call_id: number }
  | { kind: 'kpi'; name: KpiOut['name'] }
  | { kind: 'stage' }

export type ChatAskIn = {
  /** Stripped by the server; blank is 422. At most 2000 characters. */
  question: string
  /** At most 8. */
  items: AskItemRef[]
  /** null starts a new thread. */
  thread_id: number | null
}

export type AskItemOut = {
  ref: AskItemRef
  /** Built by the server from generic words, the kind and a date, e.g. "Bill, Mar 3, 2025". */
  label: string
  /** What the item resolved to, at most 50. */
  facts: FactRef[]
}

export type ChatTurnStatus = 'running' | 'done' | 'failed' | 'no_model'

/** A superset of BriefSentenceOut, so the brief's sentence component renders it. */
export type ChatSentenceOut = {
  text: string
  /** Empty only when not_in_file. */
  facts: FactRef[]
  verdict: SentenceVerdict
  mentions: DraftMentionOut[]
  not_in_file: boolean
}

export type ChatTurnOut = {
  turn_id: number
  thread_id: number
  question: string
  items: AskItemOut[]
  status: ChatTurnStatus
  /** Empty unless done. */
  sentences: ChatSentenceOut[]
  /** The model found nothing in the file that answers. */
  no_answer: boolean
  /** Sentences hidden at serve time, since a cited fact is no longer renderable. */
  withdrawn: number
  /** failed: a short reason, never record text. */
  error: string | null
  /** The answer's model call; null while running or when cached. */
  cost_micro_usd: number | null
  /** The stub user's name. */
  asked_by: string | null
  asked_at: IsoDateTime
  answered_at: IsoDateTime | null
}

export type ChatThreadOut = {
  thread_id: number
  /** The first question, cut to 80 characters. */
  title: string
  created_at: IsoDateTime
  updated_at: IsoDateTime
  /** Oldest first; a closed thread's turns as frozen when it closed (D52). */
  turns: ChatTurnOut[]
  /**
   * D52: set once the thread is closed; it takes no more questions. The server always
   * sends both fields. They are optional only until `storeTurn` in api/chat.ts seeds a
   * new thread with them (ui-builder), so test with `!= null`, not `!== null`.
   */
  closed_at?: IsoDateTime | null
  /** The stub user who closed it. */
  closed_by?: string | null
}

export type ChatThreadSummaryOut = {
  thread_id: number
  title: string
  updated_at: IsoDateTime
  turn_count: number
  last_status: ChatTurnStatus
  /** Who started the thread. */
  asked_by: string | null
  /** D52: the list holds open threads first, by updated_at, then closed ones by closed_at, newest first. */
  closed_at: IsoDateTime | null
}

export type ChatBudgetOut = {
  spent_today_micro_usd: number
  cap_micro_usd: number
  /** The next local midnight, with its offset. */
  resets_at: IsoDateTime
  /** CHAT_MODEL, the key and the chat prices are set. */
  configured: boolean
}

// --- Ops -------------------------------------------------------------------------------

export type HealthOut = {
  status: 'ok'
  clio_configured: boolean
  models_configured: boolean
}

/** A job that stopped before it wrote its run row: no Clio token, no matching matter. */
export type StartFailureOut = {
  at: IsoDateTime
  error: string
}

export type RunStatusOut = {
  running: boolean
  last_run: RunOut | null
  /** Set only while no run row is newer than the failed attempt. */
  start_failure: StartFailureOut | null
  /**
   * Digest only (null for sync): model calls a digest answers from the cache as failed.
   * Offer "retry failed calls" only when this is above zero (D29).
   */
  cached_failed_calls: number | null
}

/** Optional body of POST /api/ops/digest. */
export type DigestStartIn = {
  /** Ask the model again for calls that failed before, instead of the cached failure. */
  retry_failed: boolean
}

export type CostOut = {
  matter_id: number
  pages: number
  model_calls: number
  cache_hits: number
  input_tokens: number
  output_tokens: number
  cost_micro_usd: number
  /** D49: the chatbot's calls, kept apart; the fields above count the digest only. */
  chat_calls: number
  chat_cost_micro_usd: number
}
