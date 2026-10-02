"""The contract between the pipeline and the two views. Frozen after M0.

Three groups, in order: the `value_json` payload for each fact kind (written by the
pipeline), the documents stored in `digests` (written by the merge step), and the
request and response models for every API route. `frontend/src/api/types.ts`
mirrors this file; change both in one commit.

Money is integer cents. Dates are ISO strings in JSON.
"""

from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

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
    label: str  # neutral wording, safe to show a provider


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


class PolicyLimitPayload(FactPayload):
    amount_cents: int | None = None
    per: Literal["person", "occurrence"] | None = None


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


class PageRef(BaseModel):
    page_id: int
    page_no: int
    image_url: str


class SourceOut(BaseModel):
    source_id: int
    source_type: SourceType
    title: str | None
    occurred_on: date | None
    author: str | None  # note author or email sender
    text: str | None  # full text for notes and emails, None for documents
    pages: list[PageRef]  # every page of a document, in order; empty otherwise


class FactSourceOut(BaseModel):
    fact: FactOut
    source: SourceOut
    corroborating: list[SourceOut]


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


class KpiValueOut(BaseModel):
    amount_cents: int | None = None
    low_cents: int | None = None
    high_cents: int | None = None
    facts: list[FactRef]


class KpiOut(BaseModel):
    """One KPI tile. No values means "Not found in file"; two or more means sources disagree."""

    name: Literal["case_value", "coverage", "medical_specials", "firm_spend"]
    values: list[KpiValueOut]
    basis: str | None


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
    last_client_contact: DatedFactOut | None
    kpis: list[KpiOut]
    digested: bool  # false: synced but not digested, so the page prompts for a digest
    last_sync: RunOut | None
    last_digest: RunOut | None


class BriefSentenceOut(BaseModel):
    text: str
    facts: list[FactRef]


class BriefOut(BaseModel):
    headline: str
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
    billed_cents: int
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


class ProviderItemOut(BaseModel):
    fact_id: int
    on: date | None
    label: str
    amount_cents: int | None
    has_source: bool  # true only for this provider's own bills and records


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


# --- API: ops ------------------------------------------------------------------------


class HealthOut(BaseModel):
    status: Literal["ok"]
    clio_configured: bool
    models_configured: bool


class RunStatusOut(BaseModel):
    running: bool
    last_run: RunOut | None


class CostOut(BaseModel):
    matter_id: int
    pages: int
    model_calls: int
    cache_hits: int
    input_tokens: int
    output_tokens: int
    cost_micro_usd: int
