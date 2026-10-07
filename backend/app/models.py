"""Database tables. The schema and the reasoning behind it are in docs/architecture.md.

`matter_id` everywhere is the Clio matter id. There is no matters table: a matter
is whatever has been synced into `sources`.
"""

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any, ClassVar

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Dialect,
    Enum,
    ForeignKey,
    Index,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """A timezone-aware datetime, stored as naive UTC because SQLite has no time zones."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime; store timezone-aware values only")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        return None if value is None else value.replace(tzinfo=UTC)


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[Any, Any]] = {datetime: UTCDateTime}


def _enum_column(enum_type: type[StrEnum]) -> Enum:
    """Store a StrEnum by value in a VARCHAR, guarded by a CHECK constraint."""
    return Enum(
        enum_type,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda members: [member.value for member in members],
    )


class SourceType(StrEnum):
    MATTER = "matter"
    CUSTOM_FIELD = "custom_field"
    CONTACT = "contact"
    RELATIONSHIP = "relationship"
    NOTE = "note"
    COMMUNICATION = "communication"
    TASK = "task"
    CALENDAR_ENTRY = "calendar_entry"
    ACTIVITY = "activity"
    DOCUMENT = "document"
    # Not a Clio record: a call placed from Clarity, whose transcript its notes cite.
    CALL = "call"


class FactKind(StrEnum):
    CASE_STAGE = "case_stage"
    STATUS_CHANGE = "status_change"
    INJURY = "injury"
    DIAGNOSIS = "diagnosis"
    TREATMENT_VISIT = "treatment_visit"
    MEDICAL_BILL = "medical_bill"
    LIEN = "lien"
    RECORDS_RECEIVED = "records_received"
    RECORD_REQUEST = "record_request"
    COVERAGE = "coverage"
    POLICY_LIMIT = "policy_limit"
    CASE_VALUE = "case_value"
    LIABILITY = "liability"
    DEMAND = "demand"
    OFFER = "offer"
    SETTLEMENT = "settlement"
    EXPENSE = "expense"
    DEADLINE = "deadline"
    TASK = "task"
    CLIENT_CONTACT = "client_contact"
    PARTY = "party"
    # The two below come from mapped custom fields: the header's date of incident and
    # the KPI strip's medical specials total. No other kind can carry them.
    INCIDENT = "incident"
    MEDICAL_SPECIALS = "medical_specials"
    # D20, D21: kept apart from medical specials and case value, which they used to
    # be filed as. Economic damages are specials plus other losses (wages, for
    # example); a recovery cap is a ceiling on what the case can collect.
    ECONOMIC_DAMAGES = "economic_damages"
    RECOVERY_CAP = "recovery_cap"
    # A note taken from a call's transcript (Calls, D8). Internal by default-deny.
    CALL_NOTE = "call_note"
    OTHER = "other"


class Visibility(StrEnum):
    INTERNAL = "internal"
    SHAREABLE = "shareable"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Origin(StrEnum):
    CODE = "code"
    MODEL = "model"


class DigestKind(StrEnum):
    BRIEF = "brief"
    FIELD_MAPPING = "field_mapping"


class ShareEventType(StrEnum):
    OPENED = "opened"


class Source(Base):
    """One Clio record or document, stored as received. Parsing happens in the digest."""

    __tablename__ = "sources"
    # Contacts and custom field definitions are account-level in Clio. Keying on the
    # matter keeps each matter's copy self-contained, so one filter scopes everything.
    __table_args__ = (UniqueConstraint("matter_id", "clio_type", "clio_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    matter_id: Mapped[int] = mapped_column(index=True)
    clio_type: Mapped[SourceType] = mapped_column(_enum_column(SourceType))
    # A string because some Clio ids are strings (calendar entries).
    clio_id: Mapped[str]
    etag: Mapped[str | None]
    clio_created_at: Mapped[datetime | None]
    clio_updated_at: Mapped[datetime | None]
    raw_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    file_path: Mapped[str | None]
    content_hash: Mapped[str | None]
    synced_at: Mapped[datetime] = mapped_column(default=utcnow)

    pages: Mapped[list["Page"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class Page(Base):
    """One page of a PDF document, with its text layer and rendered image."""

    __tablename__ = "pages"
    __table_args__ = (UniqueConstraint("source_id", "page_no"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    page_no: Mapped[int]  # 1-based, as printed on the page
    has_text_layer: Mapped[bool]
    text: Mapped[str | None] = mapped_column(Text)
    image_path: Mapped[str | None]
    content_hash: Mapped[str] = mapped_column(index=True)
    extracted_at: Mapped[datetime | None]

    source: Mapped[Source] = relationship(back_populates="pages")


class Fact(Base):
    """One sourced claim. A fact without a source cannot be stored."""

    __tablename__ = "facts"
    __table_args__ = (
        CheckConstraint("significance BETWEEN 0 AND 100", name="significance_range"),
        Index("ix_facts_matter_significance", "matter_id", "significance"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    matter_id: Mapped[int] = mapped_column(index=True)
    kind: Mapped[FactKind] = mapped_column(_enum_column(FactKind))
    title: Mapped[str]
    value_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    event_date: Mapped[date | None]
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), index=True
    )
    page_no: Mapped[int | None]
    quote: Mapped[str | None] = mapped_column(Text)
    # The Clio contact this fact concerns, if any. Drives per-provider sharing.
    provider_contact_id: Mapped[int | None] = mapped_column(index=True)
    # Set by the extractor for valuation, negotiation posture, or liability opinions.
    # Such a fact is never shareable, whatever its kind.
    mentions_strategy: Mapped[bool] = mapped_column(default=False)
    visibility: Mapped[Visibility] = mapped_column(
        _enum_column(Visibility), default=Visibility.INTERNAL
    )
    significance: Mapped[int] = mapped_column(default=0)
    confidence: Mapped[Confidence] = mapped_column(_enum_column(Confidence))
    verified: Mapped[bool] = mapped_column(default=False)
    origin: Mapped[Origin] = mapped_column(_enum_column(Origin))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    source: Mapped[Source] = relationship()


class Digest(Base):
    """A merge-stage result (the brief, the field mapping) and the input it was built from."""

    __tablename__ = "digests"

    id: Mapped[int] = mapped_column(primary_key=True)
    matter_id: Mapped[int] = mapped_column(index=True)
    kind: Mapped[DigestKind] = mapped_column(_enum_column(DigestKind))
    content_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    input_hash: Mapped[str]
    model: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class LlmCall(Base):
    """One model call or cache hit. Doubles as the response cache, keyed by `cache_key`."""

    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    matter_id: Mapped[int | None] = mapped_column(index=True)
    purpose: Mapped[str]
    model: Mapped[str]
    # Hash of model, prompt version, and input content.
    cache_key: Mapped[str] = mapped_column(index=True)
    response_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    # Integer micro-dollars, so sums are exact without floats.
    cost_micro_usd: Mapped[int] = mapped_column(default=0)
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL")
    )
    page_no: Mapped[int | None]
    cache_hit: Mapped[bool] = mapped_column(default=False)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class User(Base):
    """A seeded stub account. There is no real authentication."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    role: Mapped[str]


class View(Base):
    """When a firm user last opened a matter, for the "since you last opened" block."""

    __tablename__ = "views"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    matter_id: Mapped[int] = mapped_column(primary_key=True)
    last_opened_at: Mapped[datetime]


class Share(Base):
    """A provider's link to a scoped view of one matter."""

    __tablename__ = "shares"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(unique=True)
    matter_id: Mapped[int] = mapped_column(index=True)
    provider_contact_id: Mapped[int]
    settings_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    hidden_fact_ids_json: Mapped[list[int]] = mapped_column(JSON, default=list)
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    expires_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]


class ShareEvent(Base):
    __tablename__ = "share_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    share_id: Mapped[int] = mapped_column(
        ForeignKey("shares.id", ondelete="CASCADE"), index=True
    )
    event: Mapped[ShareEventType] = mapped_column(_enum_column(ShareEventType))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class SyncRun(Base):
    """One `cli sync` run: per-type counts and any per-item errors."""

    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    matter_id: Mapped[int | None] = mapped_column(index=True)
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    finished_at: Mapped[datetime | None]
    stats_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)


class DigestRun(Base):
    """One `cli digest` run, recorded like a sync so the UI can flag a failed digest."""

    __tablename__ = "digest_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    matter_id: Mapped[int | None] = mapped_column(index=True)
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    finished_at: Mapped[datetime | None]
    stats_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)


class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    access_token: Mapped[str]
    refresh_token: Mapped[str]
    expires_at: Mapped[datetime]


class NotesStatus(StrEnum):
    NOT_STARTED = "not_started"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    NO_MODEL = "no_model"  # the model settings are missing; the transcript stands alone


class CallNumber(Base):
    """A name and number typed into Clarity to call (D15). Stored here, never in Clio."""

    __tablename__ = "call_numbers"

    id: Mapped[int] = mapped_column(primary_key=True)
    matter_id: Mapped[int] = mapped_column(index=True)
    name: Mapped[str]
    phone: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Call(Base):
    """A call placed from Clarity: whom, the consent wording confirmed, the transcript.

    Lives only in Clarity's database (rule 1). When its notes are written, the
    transcript becomes a `call` source, so each note cites it like any other record.
    """

    __tablename__ = "calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    matter_id: Mapped[int] = mapped_column(index=True)
    # The target as it stood when the call started (schemas.CallTargetOut).
    target_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    consent_text: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    ended_at: Mapped[datetime | None]
    transcript: Mapped[str] = mapped_column(Text, default="")
    transcript_final: Mapped[bool] = mapped_column(default=False)
    notes_status: Mapped[NotesStatus] = mapped_column(
        _enum_column(NotesStatus), default=NotesStatus.NOT_STARTED
    )
    notes_error: Mapped[str | None] = mapped_column(Text)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"))
