"""Read Clio records out of `sources.raw_json`, and write facts with stable rules.

Parsing lives here, not in sync, so a parsing fix never needs another sync.
"""

import hashlib
import html
import json
import re
from datetime import date, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Fact, FactKind, Origin, Source, SourceType, Visibility

# Kinds a share setting can ever release (docs/architecture.md). Anything else is
# internal. The provider filter in services/visibility.py is the real boundary; this
# only sets the stored default.
SHAREABLE_KINDS = {
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

# Keys the merge step adds or rewrites after extraction.
MERGE_KEYS = {"corroborating_source_ids", "waiting_on", "alt_values"}

_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"[ \t\r\f\v]+")


def sources_of(
    session: Session, matter_id: int, source_type: SourceType
) -> list[Source]:
    return list(
        session.scalars(
            select(Source)
            .where(Source.matter_id == matter_id, Source.clio_type == source_type)
            .order_by(Source.id)
        )
    )


def clean_text(value: Any) -> str:
    """Strip HTML from email and note bodies and collapse whitespace."""
    if not value:
        return ""
    text = str(value)
    if "<" in text and ">" in text:
        text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>", "\n", text)
        text = _TAG.sub("", text)
    text = _SPACE.sub(" ", html.unescape(text))
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def name_of(value: Any) -> str | None:
    if isinstance(value, dict):
        return value.get("name") or None
    if isinstance(value, list):
        names = [name_of(v) for v in value]
        return ", ".join(n for n in names if n) or None
    return None


def record_hash(source: Source) -> str:
    return hashlib.sha256(
        json.dumps(source.raw_json, sort_keys=True, default=str).encode()
    ).hexdigest()


def is_processed(source: Source) -> bool:
    return source.content_hash == record_hash(source)


def mark_processed(source: Source) -> None:
    source.content_hash = record_hash(source)


MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def display_date(day: date | None) -> str | None:
    """Mar 4, 2021: the way the app writes a date, so text from code matches the page."""
    if day is None:
        return None
    return f"{MONTHS[day.month - 1]} {day.day}, {day.year}"


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def record_text(source: Source) -> str:
    """The text a model reads for one note or communication.

    Custom fields are read as one record that the mapping builds (`mapping.py`).
    """
    raw = source.raw_json
    if source.clio_type is SourceType.NOTE:
        return "\n".join(
            filter(
                None,
                [
                    "Type: matter note",
                    f"Date: {raw.get('date') or raw.get('created_at')}",
                    f"Author: {name_of(raw.get('author')) or 'unknown'}",
                    f"Subject: {raw.get('subject') or ''}",
                    "Body:",
                    clean_text(raw.get("detail")),
                ],
            )
        )
    if source.clio_type is SourceType.COMMUNICATION:
        return "\n".join(
            [
                f"Type: {raw.get('type') or 'communication'}",
                f"Date: {raw.get('date') or raw.get('created_at')}",
                f"From: {name_of(raw.get('senders')) or 'unknown'}",
                f"To: {name_of(raw.get('receivers')) or 'unknown'}",
                f"Subject: {raw.get('subject') or ''}",
                "Body:",
                clean_text(raw.get("body")),
            ]
        )
    return clean_text(json.dumps(raw, default=str))


def visibility_for(kind: FactKind, mentions_strategy: bool) -> Visibility:
    if mentions_strategy or kind not in SHAREABLE_KINDS:
        return Visibility.INTERNAL
    return Visibility.SHAREABLE


def replace_facts(
    session: Session,
    source: Source,
    facts: list[Fact],
    origin: Origin,
    page_no: int | None = None,
) -> None:
    """Swap one source's (or one page's) facts of one origin for a new set.

    When the new set is identical to the stored one, nothing changes, so fact ids stay
    stable across runs. Shares refer to fact ids in their hidden list.
    """
    current = select(Fact).where(Fact.source_id == source.id, Fact.origin == origin)
    statement = delete(Fact).where(Fact.source_id == source.id, Fact.origin == origin)
    if page_no is not None:
        current = current.where(Fact.page_no == page_no)
        statement = statement.where(Fact.page_no == page_no)
    existing = list(session.scalars(current))
    if sorted(map(_signature, existing)) == sorted(
        _signature(f, page_no) for f in facts
    ):
        return
    session.execute(statement)
    for fact in facts:
        fact.source_id = source.id
        fact.matter_id = source.matter_id
        fact.origin = origin
        fact.visibility = visibility_for(fact.kind, fact.mentions_strategy)
        session.add(fact)
    session.flush()


def _signature(fact: Fact, page_no: int | None = None) -> str:
    # Keys the merge step adds later are not part of what extraction produced.
    value = {k: v for k, v in (fact.value_json or {}).items() if k not in MERGE_KEYS}
    return json.dumps(
        [
            fact.kind,
            fact.title,
            fact.quote,
            value,
            str(fact.event_date),
            fact.provider_contact_id,
            fact.page_no if fact.page_no is not None else page_no,
            bool(fact.mentions_strategy),
            fact.confidence,
            bool(fact.verified),
        ],
        sort_keys=True,
        default=str,
    )
