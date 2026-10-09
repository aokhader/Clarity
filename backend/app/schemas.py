"""The contract between the pipeline and the two views. Frozen after M0.

Three groups, in order: the `value_json` payload for each fact kind (written by the
pipeline), the documents stored in `digests` (written by the merge step), and the
request and response models for every API route. `frontend/src/api/types.ts`
mirrors this file; change both in one commit.

Money is integer cents. Dates are ISO strings in JSON.
"""

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import Confidence, FactKind, Origin, SourceType, Visibility


class CaseStage(StrEnum):
    """Canonical stages, in the order the provider tracker shows them."""

    INTAKE = "intake"
    TREATING = "treating"
    TREATMENT_COMPLETE = "treatment_complete"
    DEMAND = "demand"
    NEGOTIATION = "negotiation"
    LITIGATION = "litigation"
    SETTLED = "settled"
    CLOSED = "closed"


class ContactRole(StrEnum):
    MEDICAL_PROVIDER = "medical_provider"
    INSURER = "insurer"
    OPPOSING_PARTY = "opposing_party"
    CLIENT = "client"
    OTHER = "other"


class FieldSlot(StrEnum):
    """Canonical slots a firm's custom fields are mapped onto."""

    CASE_VALUE = "case_value"
    COVERAGE = "coverage"
    POLICY_LIMIT = "policy_limit"
    MEDICAL_SPECIALS = "medical_specials"
    DATE_OF_INCIDENT = "date_of_incident"
    STATUTE_OF_LIMITATIONS = "statute_of_limitations"


WaitingOn = Literal["firm", "client", "provider", "insurer", "court", "other"]


# --- Fact payloads (facts.value_json) --------------------------------------------


class AltValue(BaseModel):
    """A value that disagrees with the fact's own, from a second read or another source."""

    amount_cents: int | None = None
    on: date | None = None
    source_id: int | None = None
    page_no: int | None = None


class FactPayload(BaseModel):
    # Unknown keys are an error, so a payload cannot drift from this contract silently.
    model_config = ConfigDict(extra="forbid")

    alt_values: list[AltValue] = Field(default_factory=list)
    corroborating_source_ids: list[int] = Field(default_factory=list)


class CaseStagePayload(FactPayload):
    stage: CaseStage | None = None
    inferred: bool = False


class StatusChangePayload(FactPayload):
    from_stage: CaseStage | None = None
    to_stage: CaseStage | None = None
    label: str  # the record's wording, for the firm; a provider never sees it (D41)


class InjuryPayload(FactPayload):
    body_part: str | None = None
    description: str | None = None
    severity: str | None = None


class TreatmentVisitPayload(FactPayload):
    visit_type: str | None = None


class BillPayload(FactPayload):
    amount_cents: int | None = None
    balance_cents: int | None = None


class RecordsReceivedPayload(FactPayload):
    description: str | None = None
    page_count: int | None = None


class RecordRequestPayload(FactPayload):
    description: str | None = None
    status: Literal["open", "fulfilled"] = "open"


class CoveragePayload(FactPayload):
    carrier: str | None = None
    coverage_type: str | None = None
    confirmed: bool | None = None


# D19, D21: whose policy a limit belongs to. None is unknown, as on facts read before.
PolicyHolder = Literal[
    "defendant_liability", "client_no_fault", "client_um_uim", "client_other"
]


class PolicyLimitPayload(FactPayload):
    amount_cents: int | None = None
    per: Literal["person", "occurrence"] | None = None
    policy: PolicyHolder | None = None


class CaseValuePayload(FactPayload):
    low_cents: int | None = None
    high_cents: int | None = None
    basis: str | None = None


class LiabilityPayload(FactPayload):
    assessment: str | None = None


class NegotiationPayload(FactPayload):
    amount_cents: int | None = None
    party: str | None = None


class ExpensePayload(FactPayload):
    amount_cents: int | None = None
    category: str | None = None
    vendor: str | None = None


class DeadlinePayload(FactPayload):
    deadline_type: str | None = None
    due_at: datetime | None = None
    # The status of the Clio task the deadline was read from, filled when served from
    # that task's own fact (services/fact_views.py); None for any other deadline.
    status: Literal["open", "complete"] | None = None


class TaskPayload(FactPayload):
    status: Literal["open", "complete"]
    due_at: datetime | None = None
    assignee: str | None = None
    waiting_on: WaitingOn | None = None


class ClientContactPayload(FactPayload):
    channel: Literal["email", "phone", "text", "meeting", "letter", "other"] | None = (
        None
    )
    direction: Literal["inbound", "outbound"] | None = None


class PartyPayload(FactPayload):
    role: str | None = None


class IncidentPayload(FactPayload):
    description: str | None = None


class MedicalSpecialsPayload(FactPayload):
    amount_cents: int | None = None


class EconomicDamagesPayload(FactPayload):
    """Specials plus other losses. `basis` says what the total includes."""

    amount_cents: int | None = None
    basis: str | None = None


class RecoveryCapPayload(FactPayload):
    """A ceiling on what the case can recover. `basis` says what sets it."""

    amount_cents: int | None = None
    basis: str | None = None


CallNoteKind = Literal["summary", "commitment", "date", "amount", "follow_up"]


class CallNoteDate(BaseModel):
    on: date
    precision: Literal["day", "month"]


class CallNotePayload(FactPayload):
    """A note from a call. The quote is `transcript[quote_start:quote_end]`."""

    note_kind: CallNoteKind | None = None
    quote_start: int | None = None
    quote_end: int | None = None
    amounts_cents: list[int] = Field(default_factory=list)
    dates: list[CallNoteDate] = Field(default_factory=list)


LitigationEventType = Literal[
    "filed",
    "served",
    "answered",
    "dismissed",
    "renewed",
    "motion",
    "order",
    "hearing",
    "deposition",
    "trial",
    "other",
]


class LitigationEventPayload(FactPayload):
    """Something that happened in the lawsuit (D41), dated by the filing, service or
    decision date. A hearing or deposition is one that took place, not one set."""

    # "other" when the record does not say which, so a dated filing is still kept.
    event: LitigationEventType = "other"
    detail: str | None = None


class OtherPayload(FactPayload):
    detail: str | None = None


PAYLOAD_BY_KIND: dict[FactKind, type[FactPayload]] = {
    FactKind.CASE_STAGE: CaseStagePayload,
    FactKind.STATUS_CHANGE: StatusChangePayload,
    FactKind.INJURY: InjuryPayload,
    FactKind.DIAGNOSIS: InjuryPayload,
    FactKind.TREATMENT_VISIT: TreatmentVisitPayload,
    FactKind.MEDICAL_BILL: BillPayload,
    FactKind.LIEN: BillPayload,
    FactKind.RECORDS_RECEIVED: RecordsReceivedPayload,
    FactKind.RECORD_REQUEST: RecordRequestPayload,
    FactKind.COVERAGE: CoveragePayload,
    FactKind.POLICY_LIMIT: PolicyLimitPayload,
    FactKind.CASE_VALUE: CaseValuePayload,
    FactKind.LIABILITY: LiabilityPayload,
    FactKind.DEMAND: NegotiationPayload,
    FactKind.OFFER: NegotiationPayload,
    FactKind.SETTLEMENT: NegotiationPayload,
    FactKind.EXPENSE: ExpensePayload,
    FactKind.DEADLINE: DeadlinePayload,
    FactKind.TASK: TaskPayload,
    FactKind.CLIENT_CONTACT: ClientContactPayload,
    FactKind.PARTY: PartyPayload,
    FactKind.INCIDENT: IncidentPayload,
    FactKind.MEDICAL_SPECIALS: MedicalSpecialsPayload,
    FactKind.ECONOMIC_DAMAGES: EconomicDamagesPayload,
    FactKind.RECOVERY_CAP: RecoveryCapPayload,
    FactKind.CALL_NOTE: CallNotePayload,
    FactKind.LITIGATION_EVENT: LitigationEventPayload,
    FactKind.OTHER: OtherPayload,
}


def validate_payload(kind: FactKind, value: dict[str, Any]) -> dict[str, Any]:
    """Check a payload against its kind's model and return it ready for `value_json`."""
    return PAYLOAD_BY_KIND[kind].model_validate(value).model_dump(mode="json")


# --- Stored digests (digests.content_json) ---------------------------------------


class BriefSentence(BaseModel):
    text: str
    fact_ids: list[int] = Field(min_length=1)


class BriefContent(BaseModel):
    """The brief as the merge step stores it (kind `brief`)."""

    headline: str
    # The facts the headline rests on (D14). Briefs stored before D14 have none.
    headline_fact_ids: list[int] = Field(default_factory=list)
    stage: CaseStage
    stage_fact_ids: list[int]
    sentences: list[BriefSentence]
    open_questions: list[str]


class FieldMappingContent(BaseModel):
    """Contact roles and custom-field slots as the merge step stores them (kind `field_mapping`)."""

    contact_roles: dict[int, ContactRole]  # Clio contact id -> role
    field_slots: dict[int, FieldSlot]  # Clio custom field id -> slot


# --- API: facts and sources --------------------------------------------------------


class FactRef(BaseModel):
    """What a source chip needs to render and to open the drawer."""

    id: int
    source_type: SourceType
    page_no: int | None
    confidence: Confidence


class FactOut(BaseModel):
    """A fact as the firm sees it. `value` matches `PAYLOAD_BY_KIND[kind]`."""

    id: int
    kind: FactKind
    title: str
    event_date: date | None
    value: dict[str, Any]
    source_id: int
    source_type: SourceType
    page_no: int | None
    quote: str | None
    provider_contact_id: int | None
    visibility: Visibility
    significance: int
    confidence: Confidence
    verified: bool
    origin: Origin
    created_at: datetime
    # Other facts that state the same thing from other records, one per record. Filled
    # by the ranked feed and key events, which list each fact once
    # (services/restatements.py); empty elsewhere.
    restated_by: list[FactRef] = Field(default_factory=list)


class PageRef(BaseModel):
    page_id: int
    page_no: int
    image_url: str


class FirmPageOut(PageRef):
    """A document page in the firm's drawer, with its text layer as the image's text
    alternative (WCAG 1.1.1). None for a scan, which has no text layer."""

    text: str | None


class SourceFieldOut(BaseModel):
    """One labelled value of a structured record. Exactly one of the values is set."""

    label: str
    value: str | None = None
    on: date | None = None
    amount_cents: int | None = None


class SourceSectionOut(BaseModel):
    """A titled part of a structured record: labelled fields, free text, or both."""

    heading: str
    fields: list[SourceFieldOut] = []
    text: str | None = None


class SourceOut(BaseModel):
    source_id: int
    source_type: SourceType
    title: str | None
    occurred_on: date | None
    author: str | None  # note author or email sender
    text: str | None  # full text for notes and emails, None for documents
    pages: list[FirmPageOut]  # every page of a document, in order; empty otherwise
    # Matters and tasks, laid out by aspect for reading; empty for every other source.
    sections: list[SourceSectionOut] = []
    # A document's own date (its received date in Clio), when known. For a document,
    # `occurred_on` is the day it was uploaded.
    document_date: date | None = None


class FactSourceOut(BaseModel):
    fact: FactOut
    source: SourceOut
    corroborating: list[SourceOut]


# --- API: checked text -------------------------------------------------------------
# Amounts and dates in text, each checked against the file: a provider update or the
# share note (the draft checker), and the stored brief when it is served (D12).

# supported: the link already shows it. differs: the file has another value for the
# same subject. not_in_file: nothing in the file states it. do_not_send: only facts
# this link withholds state it. not_on_link (D37): a date in the file that this link
# does not carry, of a fact not sensitive enough to lock.
MentionVerdict = Literal[
    "supported", "differs", "not_in_file", "not_on_link", "do_not_send"
]
# A sentence takes its worst mention's verdict; with no amount or date it is unchecked.
SentenceVerdict = Literal[
    "supported", "differs", "not_in_file", "not_on_link", "do_not_send", "unchecked"
]


class DraftMentionOut(BaseModel):
    """One amount or date in the text, with its verdict.

    Offsets count UTF-16 code units, as JavaScript strings do, so the UI can slice the
    text it sent (for the brief, the sentence). `facts` cites the facts that state the value (supported, do_not_send)
    or the file's value (differs). A do_not_send mention carries no file value; its
    reason names the rule that withholds it (D17: firm routes only).
    """

    start: int
    end: int
    text: str
    kind: Literal["amount", "date"]
    verdict: MentionVerdict
    reason: str
    facts: list[FactRef]
    file_amount_cents: int | None  # differs only
    file_date: date | None  # differs only


# --- API: firm view ----------------------------------------------------------------


class UserOut(BaseModel):
    id: int
    name: str
    role: str


class MatterSummaryOut(BaseModel):
    matter_id: int
    display_number: str | None
    description: str | None
    client_name: str | None
    synced_at: datetime


class ClientOut(BaseModel):
    contact_id: int | None
    name: str
    avatar_url: str | None


class StageOut(BaseModel):
    stage: CaseStage | None
    label: str | None  # the stage as the firm names it in Clio
    inferred: bool
    facts: list[FactRef]


class DatedFactOut(BaseModel):
    on: date
    fact: FactRef


class IncidentAccountOut(BaseModel):
    """What happened on the incident day: the account most records read on it give."""

    text: str  # the title of the account's leading fact
    fact: FactRef  # that fact
    restated_by: list[FactRef]  # the other records that give it, one fact each


class KpiValueOut(BaseModel):
    amount_cents: int | None = None
    low_cents: int | None = None  # a low end alone means "at least"
    high_cents: int | None = None  # a high end alone means "up to"
    # What this value is, when one tile lists different kinds ("Per occurrence").
    label: str | None = None
    facts: list[FactRef]


class KpiOut(BaseModel):
    """One KPI tile. No values means "Not found in file"."""

    name: Literal["case_value", "coverage", "medical_specials", "firm_spend"]
    values: list[KpiValueOut]
    basis: str | None
    # True when two values are figures for the same thing. The Coverage tile lists
    # different policies as separate entries, which do not disagree (D19).
    sources_disagree: bool


class RunOut(BaseModel):
    id: int
    started_at: datetime
    finished_at: datetime | None
    error: str | None
    stats: dict[str, Any] | None


class MatterHeaderOut(BaseModel):
    matter_id: int
    display_number: str | None
    description: str | None
    client: ClientOut | None
    responsible_attorney: str | None
    opened_on: date | None
    stage: StageOut
    incident: DatedFactOut | None
    # Never the date-of-incident field, whose title is a label (D39). None when no
    # record read on the incident day names an event.
    incident_account: IncidentAccountOut | None
    last_client_contact: DatedFactOut | None
    kpis: list[KpiOut]
    digested: bool  # false: synced but not digested, so the page prompts for a digest
    last_sync: RunOut | None
    last_digest: RunOut | None


class BriefSentenceOut(BaseModel):
    text: str
    facts: list[FactRef]
    # D12: the sentence's amounts and dates against today's file. A differs mention
    # carries today's value and the facts that state it.
    verdict: SentenceVerdict
    mentions: list[DraftMentionOut]


class BriefOut(BaseModel):
    headline: str
    # D14: the facts the headline cites, and its amounts and dates checked like a
    # sentence's. No facts for a brief stored before D14.
    headline_facts: list[FactRef]
    headline_verdict: SentenceVerdict
    headline_mentions: list[DraftMentionOut]
    stage: CaseStage
    stage_facts: list[FactRef]
    sentences: list[BriefSentenceOut]
    open_questions: list[str]
    generated_at: datetime


class ChangesOut(BaseModel):
    last_opened_at: datetime | None  # None: this user has never opened the matter
    facts: list[FactOut]


class OpenedOut(BaseModel):
    last_opened_at: datetime


class ActionsOut(BaseModel):
    overdue: list[FactOut]
    upcoming: list[FactOut]
    waiting_on_others: list[FactOut]


# --- API: shares and the provider view -----------------------------------------


ShareSetting = Literal[
    "case_stage",
    "coverage_exists",
    "coverage_limits",
    "own_bills",
    "own_records",
    "requests",
    "treatment_activity",
]


class ShareSettings(BaseModel):
    """Section toggles, with the defaults from the visibility table in docs/architecture.md."""

    case_stage: bool = True
    coverage_exists: bool = True
    coverage_limits: bool = False
    own_bills: bool = True
    own_records: bool = True
    requests: bool = True
    treatment_activity: bool = False


class ShareStatusOut(BaseModel):
    share_id: int
    created_at: datetime
    expires_at: datetime | None
    revoked: bool
    opened_count: int
    last_opened_at: datetime | None


class ProviderOut(BaseModel):
    """A row in the providers panel."""

    contact_id: int
    name: str
    role_label: str | None  # the relationship description as written in Clio
    # None: no bill with an amount is on file. Never shown as zero (D16).
    billed_cents: int | None
    records_received: int
    open_requests: int
    share: ShareStatusOut | None


class ShareCreate(BaseModel):
    provider_contact_id: int
    settings: ShareSettings = Field(default_factory=ShareSettings)
    hidden_fact_ids: list[int] = Field(default_factory=list)
    note: str | None = None
    expires_in_days: int | None = Field(
        default=None, ge=1
    )  # None: the configured default


class ShareUpdate(BaseModel):
    """PATCH body. Only the fields present in the request are changed."""

    settings: ShareSettings | None = None
    hidden_fact_ids: list[int] | None = None
    note: str | None = None
    expires_at: datetime | None = None


class ShareOut(BaseModel):
    id: int
    matter_id: int
    provider_contact_id: int
    provider_name: str
    url: str
    settings: ShareSettings
    hidden_fact_ids: list[int]
    note: str | None
    created_by: int
    created_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None
    opened_count: int
    last_opened_at: datetime | None


# D35: what an item in the provider's bills and liens is. None in every other section.
ProviderItemKind = Literal["bill", "lien"]


class ProviderItemOut(BaseModel):
    fact_id: int
    on: date | None
    label: str
    amount_cents: int | None
    has_source: bool  # true only for this provider's own bills and records
    kind: ProviderItemKind | None = None


class ProviderBillsTotalOut(BaseModel):
    """The provider's own bills added up, each charge counted once."""

    amount_cents: int
    bill_count: int


class ProviderStatusOut(BaseModel):
    stages: list[CaseStage]  # the tracker, in order
    current: CaseStage | None
    active: bool  # the matter is open
    last_movement_on: date | None


class ProviderUpdateOut(BaseModel):
    on: date | None
    label: str


class ProviderCoverageOut(BaseModel):
    confirmed: bool | None  # None when coverage_exists is off
    limits: list[ProviderItemOut] | None  # None unless coverage_limits is on


class ProviderTreatmentOut(BaseModel):
    last_visit_month: str  # YYYY-MM, with no provider named


class ProviderPayload(BaseModel):
    """Everything a provider receives. A section is None when its setting is off."""

    provider_name: str
    patient_name: str | None
    firm_name: str | None
    shared_on: date
    expires_on: date | None
    note: str | None
    status: ProviderStatusOut | None
    updates: list[ProviderUpdateOut] | None
    coverage: ProviderCoverageOut | None
    requests: list[ProviderItemOut] | None
    bills: list[ProviderItemOut] | None
    # None when bills are not shared or none carries an amount.
    bills_total: ProviderBillsTotalOut | None
    records: list[ProviderItemOut] | None
    treatment_activity: ProviderTreatmentOut | None


class ShareItemOut(BaseModel):
    """A fact a share would release, listed in the composer with its hide control."""

    fact_id: int
    setting: ShareSetting
    title: str
    event_date: date | None
    hidden: bool


class SharePreviewOut(BaseModel):
    payload: ProviderPayload
    items: list[ShareItemOut]


class ProviderSourceOut(BaseModel):
    """The source a provider may open: one cited page of their own bill or record."""

    fact_id: int
    title: str
    quote: str | None
    page: PageRef | None


# --- API: the draft checker ---------------------------------------------------------


class DraftCheckIn(BaseModel):
    """Text a firm user means to send to a provider: an update, or the share's note."""

    text: str


class DraftShareCheckIn(BaseModel):
    """The same, before the link exists: checked against what it would release."""

    share: ShareCreate
    text: str


class NoteLockedOut(BaseModel):
    """The 422 body when a share's note would disclose what the link withholds (D25).

    Rule 4: the server refuses the note, so no client can send it by skipping the lock.
    """

    message: str
    locked: list[DraftMentionOut]  # offsets into the note


class DraftSentenceOut(BaseModel):
    start: int
    end: int
    text: str
    verdict: SentenceVerdict
    mentions: list[DraftMentionOut]


class DraftCheckOut(BaseModel):
    # The worst verdict of any sentence; unchecked when nothing could be checked.
    verdict: SentenceVerdict
    sentences: list[DraftSentenceOut]


# --- API: calls (docs/calls-contract.md; D8, D15, D22, D23) -------------------------

CallRole = Literal["client", "provider", "insurer", "other"]
NotesStatusOut = Literal["not_started", "running", "done", "failed", "no_model"]


class CallTargetOut(BaseModel):
    target_id: str  # "contact:<clio id>" or "entered:<id>"
    name: str | None
    role: CallRole
    phone: str | None  # None: no number on file; the UI offers to type one
    phone_source: Literal["clio", "entered"] | None
    reason: str | None  # the open item that makes this call due, in a few words
    reason_fact: FactRef | None  # that item's source, for its chip
    last_contact_days: int | None  # None means no contact found, never zero
    # The record behind last_contact_days, for its chip (rule 3, D23).
    last_contact_fact: FactRef | None


class CallNumberIn(BaseModel):
    name: str = Field(min_length=1)  # who the number belongs to, as typed
    phone: str = Field(min_length=1)


class CallStartIn(BaseModel):
    target_id: str
    consent_confirmed: bool  # must be true; 422 otherwise
    consent_text: str = Field(min_length=1)  # the wording the attorney confirmed


class CallTranscriptIn(BaseModel):
    text: str  # the whole transcript so far; the client saves every few seconds
    final: bool  # true once the call has ended


class CallOut(BaseModel):
    call_id: int
    target: CallTargetOut
    started_at: datetime
    ended_at: datetime | None
    consent_text: str
    notes_status: NotesStatusOut


class CallNoteOut(BaseModel):
    fact: FactRef  # the stored fact; its source is the transcript
    kind: CallNoteKind
    text: str
    quote_start: int  # character offsets into the transcript
    quote_end: int


class CallDetailOut(BaseModel):
    call: CallOut
    transcript: str
    notes: list[CallNoteOut]


# --- API: chat (D49) ------------------------------------------------------------------
# The client points at items by id; the server resolves and labels each one inside the
# matter (docs/chat-contract.md).


class AskFactsRef(BaseModel):
    kind: Literal["facts"] = "facts"
    fact_ids: list[int] = Field(min_length=1, max_length=50)


class AskSourceRef(BaseModel):
    kind: Literal["source"] = "source"
    source_id: int


class AskProviderRef(BaseModel):
    kind: Literal["provider"] = "provider"
    contact_id: int  # Clio contact id, as ProviderOut.contact_id


class AskCallRef(BaseModel):
    kind: Literal["call"] = "call"
    call_id: int


class AskKpiRef(BaseModel):
    kind: Literal["kpi"] = "kpi"
    name: Literal["case_value", "coverage", "medical_specials", "firm_spend"]  # KpiOut.name


class AskStageRef(BaseModel):
    kind: Literal["stage"] = "stage"


AskItemRef = Annotated[
    AskFactsRef | AskSourceRef | AskProviderRef | AskCallRef | AskKpiRef | AskStageRef,
    Field(discriminator="kind"),
]


class ChatAskIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)  # stripped; blank is 422
    items: list[AskItemRef] = Field(default_factory=list, max_length=8)
    thread_id: int | None = None  # None starts a new thread

    @field_validator("question")
    @classmethod
    def _question_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question is blank")
        return stripped


class AskItemOut(BaseModel):
    ref: AskItemRef
    # Built by the server from generic words, the kind and a date, e.g. "Bill, Mar 3, 2025".
    label: str
    facts: list[FactRef]  # what the item resolved to, at most 50


ChatTurnStatus = Literal["running", "done", "failed", "no_model"]


class ChatSentenceOut(BaseModel):
    # A superset of BriefSentenceOut, so the brief's sentence component renders it.
    text: str
    facts: list[FactRef]  # empty only when not_in_file
    verdict: SentenceVerdict
    mentions: list[DraftMentionOut]
    not_in_file: bool


class ChatTurnOut(BaseModel):
    turn_id: int
    thread_id: int
    question: str
    items: list[AskItemOut]
    status: ChatTurnStatus
    sentences: list[ChatSentenceOut]  # empty unless done
    no_answer: bool  # the model found nothing in the file that answers
    # Sentences hidden at serve time, since a cited fact is no longer renderable.
    withdrawn: int
    error: str | None  # failed: a short reason, never record text
    cost_micro_usd: int | None  # the answer's model call, None while running or when cached
    asked_by: str | None  # the stub user's name
    asked_at: datetime
    answered_at: datetime | None


class ChatThreadOut(BaseModel):
    thread_id: int
    title: str  # the first question, cut to 80 characters
    created_at: datetime
    updated_at: datetime
    turns: list[ChatTurnOut]  # oldest first


class ChatThreadSummaryOut(BaseModel):
    thread_id: int
    title: str
    updated_at: datetime
    turn_count: int
    last_status: ChatTurnStatus
    asked_by: str | None  # who started the thread


class ChatBudgetOut(BaseModel):
    spent_today_micro_usd: int
    cap_micro_usd: int
    resets_at: datetime  # the next local midnight, timezone-aware
    configured: bool  # CHAT_MODEL, the key and the chat prices are set


# --- API: ops ------------------------------------------------------------------------


class HealthOut(BaseModel):
    status: Literal["ok"]
    clio_configured: bool
    models_configured: bool


class StartFailureOut(BaseModel):
    """A job that stopped before it wrote its run row: no Clio token, no matching matter."""

    at: datetime
    error: str


class RunStatusOut(BaseModel):
    running: bool
    last_run: RunOut | None
    # Set only while no run row is newer than the failed attempt.
    start_failure: StartFailureOut | None
    # Digest only (None for sync): model calls a digest answers from the cache as
    # failed. Above zero, a digest with retry_failed asks the model again (D29).
    cached_failed_calls: int | None = None


class DigestStartIn(BaseModel):
    """Optional body of POST /api/ops/digest."""

    # Ask the model again for calls that failed before, instead of the cached failure.
    retry_failed: bool = False


class CostOut(BaseModel):
    matter_id: int
    pages: int
    model_calls: int
    cache_hits: int
    input_tokens: int
    output_tokens: int
    cost_micro_usd: int
    # D49: the chatbot's calls, kept apart; the fields above count the digest only.
    chat_calls: int
    chat_cost_micro_usd: int
