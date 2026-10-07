"""An invented personal-injury matter for development and tests.

Loaded by `python -m app.cli seed-dev` and by the test suite. Every person, company,
date, amount, and document here is made up. It writes the same tables the pipeline
writes, so the firm and provider views can be built before a real sync. The demo
runs on a live Clio sync, never on this.

Dates are relative to the day the seed runs, so overdue items stay overdue.
"""

import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import pymupdf
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Confidence,
    Digest,
    DigestKind,
    DigestRun,
    Fact,
    FactKind,
    Origin,
    Page,
    Share,
    Source,
    SourceType,
    SyncRun,
    View,
    Visibility,
)
from app.schemas import (
    BriefContent,
    CaseStage,
    ContactRole,
    FieldMappingContent,
    FieldSlot,
    validate_payload,
)

# Real Clio ids are large, so these cannot collide with a synced matter.
MATTER_ID = 1
CLIENT_ID = 101
ORTHO_ID = 201  # first medical provider
THERAPY_ID = 202  # second medical provider
INSURER_ID = 301
DOCUMENT_ID = "1001"

# Mirrors the visibility table in docs/architecture.md. Default-deny.
_SHAREABLE_KINDS = {
    FactKind.CASE_STAGE,
    FactKind.STATUS_CHANGE,
    FactKind.COVERAGE,
    FactKind.POLICY_LIMIT,
    FactKind.MEDICAL_BILL,
    FactKind.LIEN,
    FactKind.RECORDS_RECEIVED,
    FactKind.RECORD_REQUEST,
    FactKind.TASK,
    FactKind.TREATMENT_VISIT,
}

_PAGE_ONE = """NORTHSIDE ORTHOPEDICS (DEMO)
Office visit note
Patient: Jordan Avery
Assessment: Cervical strain with radiating neck pain after a vehicle collision.
Plan: Physical therapy twice weekly for six weeks.
Records enclosed: 2 pages."""

_PAGE_TWO = """STATEMENT OF CHARGES
Office visit and evaluation      $480.00
Cervical spine MRI               $2,000.00
Total charges                    $2,480.00
Balance due                      $2,480.00
MRI impression: disc herniation at L4-L5.
This office asserts a lien on any recovery for the balance due."""

# A call placed from Clarity to the first provider, and the span its note quotes.
_CALL_TRANSCRIPT = (
    "Thanks for calling. The office said the updated records will go out by Friday."
)
_CALL_QUOTE = "the updated records will go out by Friday"
_CALL_QUOTE_START = _CALL_TRANSCRIPT.index(_CALL_QUOTE)

_NOTE = (
    "Client was rear-ended at a stoplight. The other driver's carrier is Example "
    "Mutual Insurance, and the adjuster confirmed bodily injury coverage is in place. "
    "Adjuster mentioned a $50,000 per person limit. Police report places fault on the "
    "other driver. Client prefers text messages over calls. Client authorized "
    "settlement at no less than $90,000. Economic damages come to $8,440 with lost "
    "wages. Recovery is capped at the $100,000 limit."
)


@dataclass(frozen=True)
class _SourceSpec:
    clio_type: SourceType
    clio_id: str
    raw: dict[str, Any]
    created_days_ago: int


@dataclass(frozen=True)
class _FactSpec:
    kind: FactKind
    title: str
    source: str
    value: dict[str, Any]
    quote: str
    significance: int
    event_date: date | None = None
    page_no: int | None = None
    provider: int | None = None
    confidence: Confidence = Confidence.HIGH
    origin: Origin = Origin.MODEL
    mentions_strategy: bool = False


def _sources(today: date) -> dict[str, _SourceSpec]:
    def on(days: int) -> str:
        return (today + timedelta(days=days)).isoformat()

    def contact(cid: int, name: str, kind: str) -> dict[str, Any]:
        return {"id": cid, "name": name, "type": kind}

    def email(
        cid: int,
        subject: str,
        body: str,
        sender: dict[str, Any],
        to: dict[str, Any],
        d: int,
    ) -> dict[str, Any]:
        raw = {
            "id": cid,
            "subject": subject,
            "body": body,
            "type": "EmailCommunication",
        }
        return raw | {"date": on(d), "senders": [sender], "receivers": [to]}

    firm = {"id": 1, "name": "Firm Intake", "type": "User"}
    client = contact(CLIENT_ID, "Jordan Avery", "Person")
    ortho = contact(ORTHO_ID, "Northside Orthopedics (Demo)", "Company")
    therapy = contact(THERAPY_ID, "Lakeview Physical Therapy (Demo)", "Company")
    insurer = contact(INSURER_ID, "Example Mutual Insurance", "Company")
    fields = [
        (11, "Loss date", on(-210)),
        (12, "Value estimate", "75,000 - 150,000"),
        (13, "Liability limit", "100000"),
        (14, "Specials to date", "3440.00"),
    ]
    matter = {
        "id": MATTER_ID,
        "display_number": "00001-Avery",
        "description": "Avery - motor vehicle collision",
        "status": "Open",
        "open_date": on(-200),
        "practice_area": {"name": "Personal Injury"},
        "matter_stage": {"name": "Treatment"},
        "client": {"id": CLIENT_ID, "name": "Jordan Avery"},
        "responsible_attorney": {"name": "Sample Attorney"},
        "custom_field_values": [
            {"id": f"text_line-{fid}", "field_name": name, "value": value}
            | {"custom_field": {"id": fid}}
            for fid, name, value in fields
        ],
    }
    specs = [
        ("matter", SourceType.MATTER, MATTER_ID, matter, 200),
        *(
            (
                f"field_{fid}",
                SourceType.CUSTOM_FIELD,
                fid,
                {"id": fid, "name": name},
                300,
            )
            for fid, name, _ in fields
        ),
        *(
            (f"contact_{c['id']}", SourceType.CONTACT, c["id"], c, 200)
            for c in (client, ortho, therapy, insurer)
        ),
        *(
            (f"rel_{rid}", SourceType.RELATIONSHIP, rid, {"id": rid} | rel, 190)
            for rid, rel in (
                (401, {"description": "Treating physician", "contact": ortho}),
                (402, {"description": "Physical therapist", "contact": therapy}),
                (403, {"description": "Defendant's insurer", "contact": insurer}),
            )
        ),
        (
            "note",
            SourceType.NOTE,
            501,
            {"id": 501, "subject": "Intake call"}
            | {"detail": _NOTE, "date": on(-198), "author": {"name": "Firm Intake"}},
            198,
        ),
        (
            "email_therapy",
            SourceType.COMMUNICATION,
            601,
            email(
                601,
                "Therapy update",
                "Jordan attended a physical therapy session this week. Our charges to date "
                "are $960.00. Please confirm the lien on file.",
                therapy,
                firm,
                -20,
            ),
            20,
        ),
        (
            "email_client",
            SourceType.COMMUNICATION,
            602,
            email(
                602,
                "Checking in",
                "Hi, just checking in on my case. My neck still hurts.",
                client,
                firm,
                -12,
            ),
            12,
        ),
        (
            "email_demand",
            SourceType.COMMUNICATION,
            603,
            email(
                603,
                "Policy limits demand",
                "Our client demands $150,000 to resolve this claim.",
                firm,
                insurer,
                -30,
            ),
            30,
        ),
        (
            "email_offer",
            SourceType.COMMUNICATION,
            604,
            email(
                604,
                "Re: Policy limits demand",
                "We can offer $40,000 at this time.",
                insurer,
                firm,
                -6,
            ),
            6,
        ),
        *(
            (
                f"task_{tid}",
                SourceType.TASK,
                tid,
                {"id": tid, "name": name}
                | {"status": status, "due_at": on(due), "assignee": {"name": who}},
                40,
            )
            for tid, name, status, due, who in (
                (
                    701,
                    "Request updated records from Northside Orthopedics (Demo)",
                    "pending",
                    -5,
                    "Paralegal",
                ),
                (702, "Draft demand letter", "pending", 10, "Attorney"),
                (703, "Confirm policy limits with adjuster", "pending", 3, "Paralegal"),
                (704, "Send intake packet", "complete", -190, "Paralegal"),
            )
        ),
        (
            "cal_sol",
            SourceType.CALENDAR_ENTRY,
            "801",
            {"id": "801"}
            | {
                "summary": "Statute of limitations",
                "start_at": on(520),
                "all_day": True,
            },
            190,
        ),
        (
            "cal_checkin",
            SourceType.CALENDAR_ENTRY,
            "802",
            {"id": "802"}
            | {"summary": "Client check-in call", "start_at": on(7), "all_day": False},
            10,
        ),
        (
            "expense_records",
            SourceType.ACTIVITY,
            901,
            {"id": 901, "type": "ExpenseEntry"}
            | {"date": on(-60), "total": 45.0, "note": "Medical records copy fee"},
            60,
        ),
        (
            "expense_police",
            SourceType.ACTIVITY,
            902,
            {"id": 902, "type": "HardCostEntry"}
            | {"date": on(-180), "total": 15.0, "note": "Police report fee"},
            180,
        ),
        (
            "document",
            SourceType.DOCUMENT,
            DOCUMENT_ID,
            {"id": int(DOCUMENT_ID)}
            | {"name": "Orthopedic visit note and bill", "filename": "ortho-visit.pdf"},
            45,
        ),
        (
            "call",
            SourceType.CALL,
            "call-1",
            {"call_id": 1, "name": "Northside Orthopedics (Demo)", "role": "provider"}
            | {"transcript": _CALL_TRANSCRIPT},
            2,
        ),
    ]
    return {
        key: _SourceSpec(t, str(cid), raw, days) for key, t, cid, raw, days in specs
    }


def _facts(today: date) -> dict[str, _FactSpec]:
    def on(days: int) -> date:
        return today + timedelta(days=days)

    def at(days: int) -> str:
        return datetime.combine(on(days), time(17, 0), UTC).isoformat()

    code = Origin.CODE
    f = _FactSpec
    return {
        "stage": f(
            FactKind.CASE_STAGE,
            "Treatment",
            "matter",
            {"stage": CaseStage.TREATING},
            "Treatment",
            80,
            on(-150),
            origin=code,
        ),
        "status": f(
            FactKind.STATUS_CHANGE,
            "Moved to treatment",
            "matter",
            {
                "from_stage": CaseStage.INTAKE,
                "to_stage": CaseStage.TREATING,
                "label": "Client is in treatment",
            },
            "Treatment",
            60,
            on(-150),
            origin=code,
        ),
        "incident": f(
            FactKind.INCIDENT,
            "Motor vehicle collision",
            "matter",
            {"description": "Rear-end collision"},
            on(-210).isoformat(),
            85,
            on(-210),
            origin=code,
        ),
        "value": f(
            FactKind.CASE_VALUE,
            "Case valued at $75,000 to $150,000",
            "matter",
            {
                "low_cents": 7_500_000,
                "high_cents": 15_000_000,
                "basis": "Value estimate field",
            },
            "75,000 - 150,000",
            95,
            origin=code,
            mentions_strategy=True,
        ),
        "limit_field": f(
            FactKind.POLICY_LIMIT,
            "Policy limit $100,000 per person",
            "matter",
            {"amount_cents": 10_000_000, "per": "person"},
            "100000",
            92,
            origin=code,
        ),
        "limit_note": f(
            FactKind.POLICY_LIMIT,
            "Adjuster cited a $50,000 limit",
            "note",
            {"amount_cents": 5_000_000, "per": "person"},
            "Adjuster mentioned a $50,000 per person limit",
            90,
            on(-198),
        ),
        "specials": f(
            FactKind.MEDICAL_SPECIALS,
            "Medical specials $3,440",
            "matter",
            {"amount_cents": 344_000},
            "3440.00",
            75,
            origin=code,
        ),
        "damages": f(
            FactKind.ECONOMIC_DAMAGES,
            "Economic damages $8,440",
            "note",
            {"amount_cents": 844_000, "basis": "specials plus $5,000 in lost wages"},
            "Economic damages come to $8,440 with lost wages",
            70,
            on(-198),
        ),
        "cap": f(
            FactKind.RECOVERY_CAP,
            "Recovery capped at the policy limit",
            "note",
            {"amount_cents": 10_000_000, "basis": "the other driver's limit"},
            "Recovery is capped at the $100,000 limit",
            80,
            on(-198),
        ),
        "call_note": f(
            FactKind.CALL_NOTE,
            "The office will send updated records by Friday",
            "call",
            {
                "note_kind": "commitment",
                "quote_start": _CALL_QUOTE_START,
                "quote_end": _CALL_QUOTE_START + len(_CALL_QUOTE),
            },
            _CALL_QUOTE,
            80,
            on(-2),
            provider=ORTHO_ID,
        ),
        "coverage": f(
            FactKind.COVERAGE,
            "Bodily injury coverage confirmed",
            "note",
            {
                "carrier": "Example Mutual Insurance",
                "coverage_type": "bodily injury",
                "confirmed": True,
            },
            "the adjuster confirmed bodily injury coverage is in place",
            93,
            on(-198),
        ),
        "liability": f(
            FactKind.LIABILITY,
            "Police report faults other driver",
            "note",
            {"assessment": "Other driver at fault"},
            "Police report places fault on the other driver",
            91,
            on(-198),
            mentions_strategy=True,
        ),
        "settlement": f(
            FactKind.SETTLEMENT,
            "Client set $90,000 settlement floor",
            "note",
            {"amount_cents": 9_000_000, "party": "client"},
            "Client authorized settlement at no less than $90,000",
            96,
            on(-198),
            mentions_strategy=True,
        ),
        "preference": f(
            FactKind.OTHER,
            "Client prefers text messages",
            "note",
            {"detail": "Contact preference"},
            "Client prefers text messages over calls",
            20,
            on(-198),
        ),
        "injury": f(
            FactKind.INJURY,
            "Cervical strain with neck pain",
            "document",
            {
                "body_part": "neck",
                "description": "Cervical strain",
                "severity": "moderate",
            },
            "Cervical strain with radiating neck pain",
            85,
            on(-45),
            page_no=1,
            provider=ORTHO_ID,
        ),
        "diagnosis": f(
            FactKind.DIAGNOSIS,
            "Disc herniation at L4-L5",
            "document",
            {"body_part": "lower back", "description": "Disc herniation"},
            "MRI impression: disc herniation at L4-L5.",
            88,
            on(-45),
            page_no=2,
            provider=ORTHO_ID,
            confidence=Confidence.MEDIUM,
        ),
        "visit_ortho": f(
            FactKind.TREATMENT_VISIT,
            "Orthopedic office visit",
            "document",
            {"visit_type": "orthopedic consult"},
            "Office visit note",
            50,
            on(-45),
            page_no=1,
            provider=ORTHO_ID,
        ),
        "records_ortho": f(
            FactKind.RECORDS_RECEIVED,
            "Orthopedic records received",
            "document",
            {"description": "Visit note", "page_count": 2},
            "Records enclosed: 2 pages.",
            55,
            on(-45),
            page_no=1,
            provider=ORTHO_ID,
        ),
        # The second read of this scanned total disagreed, so it carries both values.
        "bill_ortho": f(
            FactKind.MEDICAL_BILL,
            "Orthopedic charges $2,480",
            "document",
            {
                "amount_cents": 248_000,
                "balance_cents": 248_000,
                "alt_values": [{"amount_cents": 284_000, "page_no": 2}],
            },
            "Total charges $2,480.00",
            65,
            on(-45),
            page_no=2,
            provider=ORTHO_ID,
            confidence=Confidence.LOW,
        ),
        "lien_ortho": f(
            FactKind.LIEN,
            "Orthopedic lien for $2,480",
            "document",
            {"amount_cents": 248_000, "balance_cents": 248_000},
            "This office asserts a lien on any recovery",
            78,
            on(-45),
            page_no=2,
            provider=ORTHO_ID,
            confidence=Confidence.MEDIUM,
        ),
        "visit_therapy": f(
            FactKind.TREATMENT_VISIT,
            "Physical therapy session",
            "email_therapy",
            {"visit_type": "physical therapy"},
            "Jordan attended a physical therapy session this week",
            45,
            on(-20),
            provider=THERAPY_ID,
        ),
        "bill_therapy": f(
            FactKind.MEDICAL_BILL,
            "Therapy charges $960",
            "email_therapy",
            {"amount_cents": 96_000},
            "Our charges to date are $960.00",
            60,
            on(-20),
            provider=THERAPY_ID,
        ),
        "client_contact": f(
            FactKind.CLIENT_CONTACT,
            "Client emailed for an update",
            "email_client",
            {"channel": "email", "direction": "inbound"},
            "just checking in on my case",
            35,
            on(-12),
            origin=code,
        ),
        "demand": f(
            FactKind.DEMAND,
            "Demanded $150,000",
            "email_demand",
            {"amount_cents": 15_000_000, "party": "insurer"},
            "Our client demands $150,000",
            97,
            on(-30),
        ),
        "offer": f(
            FactKind.OFFER,
            "Insurer offered $40,000",
            "email_offer",
            {"amount_cents": 4_000_000, "party": "insurer"},
            "We can offer $40,000 at this time.",
            98,
            on(-6),
        ),
        "task_records": f(
            FactKind.TASK,
            "Request updated orthopedic records",
            "task_701",
            {
                "status": "open",
                "due_at": at(-5),
                "assignee": "Paralegal",
                "waiting_on": "provider",
            },
            "Request updated records from Northside Orthopedics (Demo)",
            70,
            on(-5),
            provider=ORTHO_ID,
            origin=code,
        ),
        "request_records": f(
            FactKind.RECORD_REQUEST,
            "Updated records requested",
            "task_701",
            {"description": "Updated visit records"},
            "Request updated records from Northside Orthopedics (Demo)",
            72,
            on(-5),
            provider=ORTHO_ID,
            origin=code,
        ),
        "task_demand": f(
            FactKind.TASK,
            "Draft demand letter",
            "task_702",
            {
                "status": "open",
                "due_at": at(10),
                "assignee": "Attorney",
                "waiting_on": "firm",
            },
            "Draft demand letter",
            60,
            on(10),
            origin=code,
        ),
        "task_limits": f(
            FactKind.TASK,
            "Confirm policy limits with adjuster",
            "task_703",
            {
                "status": "open",
                "due_at": at(3),
                "assignee": "Paralegal",
                "waiting_on": "insurer",
            },
            "Confirm policy limits with adjuster",
            65,
            on(3),
            origin=code,
        ),
        "task_intake": f(
            FactKind.TASK,
            "Send intake packet",
            "task_704",
            {
                "status": "complete",
                "due_at": at(-190),
                "assignee": "Paralegal",
                "waiting_on": "firm",
            },
            "Send intake packet",
            15,
            on(-190),
            origin=code,
        ),
        "sol": f(
            FactKind.DEADLINE,
            "Statute of limitations",
            "cal_sol",
            {"deadline_type": "statute_of_limitations", "due_at": at(520)},
            "Statute of limitations",
            95,
            on(520),
            origin=code,
        ),
        "checkin": f(
            FactKind.DEADLINE,
            "Client check-in call",
            "cal_checkin",
            {"deadline_type": "appointment", "due_at": at(7)},
            "Client check-in call",
            30,
            on(7),
            origin=code,
        ),
        "expense_records": f(
            FactKind.EXPENSE,
            "Records copy fee $45",
            "expense_records",
            {
                "amount_cents": 4_500,
                "category": "records",
                "vendor": "Northside Orthopedics (Demo)",
            },
            "Medical records copy fee",
            25,
            on(-60),
            origin=code,
        ),
        "expense_police": f(
            FactKind.EXPENSE,
            "Police report fee $15",
            "expense_police",
            {"amount_cents": 1_500, "category": "records"},
            "Police report fee",
            20,
            on(-180),
            origin=code,
        ),
        "party_insurer": f(
            FactKind.PARTY,
            "Example Mutual Insurance",
            "rel_403",
            {"role": "Defendant's insurer"},
            "Defendant's insurer",
            40,
            origin=code,
        ),
    }


_BRIEF = [
    (
        "The client was rear-ended and is still treating for neck and back injuries.",
        ["incident", "injury", "diagnosis"],
    ),
    (
        (
            "The insurer confirmed bodily injury coverage, but the file disagrees on "
            "the per-person limit."
        ),
        ["coverage", "limit_field", "limit_note"],
    ),
    (
        "Two providers have billed about $3,440, and the orthopedic office asserts a lien.",
        ["specials", "bill_ortho", "bill_therapy", "lien_ortho"],
    ),
    (
        "The firm demanded $150,000 and the insurer has offered $40,000.",
        ["demand", "offer"],
    ),
    (
        "A request for updated orthopedic records is overdue.",
        ["task_records", "request_records"],
    ),
    ("The statute of limitations is more than a year away.", ["sol"]),
]


def _write_document(rel_path: str) -> list[tuple[bytes, str | None]]:
    """Write a two-page PDF: page one has a text layer, page two is an image-only scan.

    Returns each page's rendered PNG bytes and its text layer (None for the scan).
    """
    settings = get_settings()
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 90), _PAGE_ONE, fontsize=11)
    scratch = pymupdf.open()
    scratch.new_page().insert_text((72, 90), _PAGE_TWO, fontsize=11)
    scan = doc.new_page()
    scan.insert_image(scan.rect, pixmap=scratch[0].get_pixmap(dpi=150))
    doc.save(settings.data_dir / rel_path)
    pages = []
    for page in doc:
        text = page.get_text().strip()
        # The same threshold the pipeline uses to tell a scan from a text page.
        pages.append(
            (page.get_pixmap(dpi=150).tobytes("png"), text if len(text) >= 50 else None)
        )
    return pages


def _clear(session: Session) -> None:
    for model in (Share, View, Digest, SyncRun, DigestRun, Source):
        session.execute(delete(model).where(model.matter_id == MATTER_ID))


def load_synthetic_matter(session: Session) -> int:
    """Replace the synthetic matter with a fresh copy. The caller commits."""
    settings = get_settings()
    now = datetime.now(UTC)
    today = now.date()
    _clear(session)

    sources: dict[str, Source] = {}
    for key, spec in _sources(today).items():
        created = now - timedelta(days=spec.created_days_ago)
        sources[key] = Source(
            matter_id=MATTER_ID,
            clio_type=spec.clio_type,
            clio_id=spec.clio_id,
            etag=f"synthetic-{spec.clio_id}",
            clio_created_at=created,
            clio_updated_at=created,
            raw_json=spec.raw,
            synced_at=now,
        )
    document = sources["document"]
    document.file_path = f"files/synthetic-{DOCUMENT_ID}.pdf"
    session.add_all(sources.values())
    session.flush()

    for page_no, (png, text) in enumerate(_write_document(document.file_path), start=1):
        image_path = f"pages/synthetic-{DOCUMENT_ID}-p{page_no}.png"
        (settings.data_dir / image_path).write_bytes(png)
        digest_input = text.encode() if text is not None else png
        session.add(
            Page(
                source_id=document.id,
                page_no=page_no,
                has_text_layer=text is not None,
                text=text,
                image_path=image_path,
                content_hash=hashlib.sha256(digest_input).hexdigest(),
                extracted_at=now,
            )
        )

    facts: dict[str, Fact] = {}
    for key, spec in _facts(today).items():
        shareable = spec.kind in _SHAREABLE_KINDS and not spec.mentions_strategy
        facts[key] = Fact(
            matter_id=MATTER_ID,
            kind=spec.kind,
            title=spec.title,
            value_json=validate_payload(spec.kind, spec.value),
            event_date=spec.event_date,
            source_id=sources[spec.source].id,
            page_no=spec.page_no,
            quote=spec.quote,
            provider_contact_id=spec.provider,
            mentions_strategy=spec.mentions_strategy,
            visibility=Visibility.SHAREABLE if shareable else Visibility.INTERNAL,
            significance=spec.significance,
            confidence=spec.confidence,
            verified=spec.confidence is Confidence.HIGH,
            origin=spec.origin,
        )
    session.add_all(facts.values())
    session.flush()

    brief = BriefContent(
        headline="Client still treating; coverage confirmed, $40,000 offer on the table, "
        "records request overdue.",
        stage=CaseStage.TREATING,
        stage_fact_ids=[facts["stage"].id],
        sentences=[
            {"text": text, "fact_ids": [facts[k].id for k in keys]}
            for text, keys in _BRIEF
        ],
        open_questions=[
            "Has the client finished physical therapy?",
            "Is there underinsured motorist coverage?",
        ],
    )
    mapping = FieldMappingContent(
        contact_roles={
            CLIENT_ID: ContactRole.CLIENT,
            ORTHO_ID: ContactRole.MEDICAL_PROVIDER,
            THERAPY_ID: ContactRole.MEDICAL_PROVIDER,
            INSURER_ID: ContactRole.INSURER,
        },
        field_slots={
            11: FieldSlot.DATE_OF_INCIDENT,
            12: FieldSlot.CASE_VALUE,
            13: FieldSlot.POLICY_LIMIT,
            14: FieldSlot.MEDICAL_SPECIALS,
        },
    )
    for kind, content in (
        (DigestKind.BRIEF, brief),
        (DigestKind.FIELD_MAPPING, mapping),
    ):
        session.add(
            Digest(
                matter_id=MATTER_ID,
                kind=kind,
                content_json=content.model_dump(mode="json"),
                input_hash="synthetic",
                model="synthetic-seed",
            )
        )

    stats = {"seed": "synthetic", "sources": len(sources), "facts": len(facts)}
    session.add(
        SyncRun(matter_id=MATTER_ID, started_at=now, finished_at=now, stats_json=stats)
    )
    session.add(
        DigestRun(
            matter_id=MATTER_ID, started_at=now, finished_at=now, stats_json=stats
        )
    )
    session.flush()
    return MATTER_ID
