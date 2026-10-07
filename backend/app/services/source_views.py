"""The source drawer: a fact's source record made readable, and rendered page images."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Fact, Page, Source, SourceType
from app.schemas import (
    PAYLOAD_BY_KIND,
    FactSourceOut,
    PageRef,
    SourceFieldOut,
    SourceOut,
    SourceSectionOut,
)
from app.services.clio_records import (
    CustomFieldValue,
    Named,
    RawActivity,
    RawCalendarEntry,
    RawCommunication,
    RawContact,
    RawDocument,
    RawMatter,
    RawNote,
    RawRelationship,
    RawTask,
)
from app.services.fact_views import fact_out, renderable_facts


class FactNotFound(LookupError):
    pass


class PageNotFound(LookupError):
    pass


class _Readable(NamedTuple):
    title: str | None
    occurred_on: date | None
    author: str | None
    text: str | None
    sections: tuple[SourceSectionOut, ...] = ()


def _day(value: datetime | date | None) -> date | None:
    return value.date() if isinstance(value, datetime) else value


def _name(named: Named | None) -> str | None:
    return named.name if named else None


def _lines(*parts: str | None) -> str | None:
    return "\n".join(p for p in parts if p) or None


def _words(code: str | None) -> str | None:
    """A Clio code such as "in_progress", as words."""
    return code.replace("_", " ").capitalize() if code else None


def _field(label: str, value: str | float | bool | None) -> SourceFieldOut | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return SourceFieldOut(label=label, value="Yes" if value else "No")
    if isinstance(value, float) and value.is_integer():
        return SourceFieldOut(label=label, value=str(int(value)))
    return SourceFieldOut(label=label, value=str(value))


def _custom_field(field: CustomFieldValue) -> SourceFieldOut | None:
    """A custom field by its Clio type, so money and dates reach the page as values."""
    label, value = field.field_name or "", field.value
    if value is None or value == "" or isinstance(value, bool):
        return _field(label, value)
    if field.field_type == "currency":
        # Through the string, so a float such as 0.1 does not become 0.1000000000000000055.
        try:
            cents = Decimal(str(value)) * 100
        except InvalidOperation:
            return _field(label, value)
        return SourceFieldOut(label=label, amount_cents=int(cents.to_integral_value()))
    if field.field_type == "date" and isinstance(value, str):
        try:
            return SourceFieldOut(label=label, on=date.fromisoformat(value[:10]))
        except ValueError:
            pass
    return _field(label, value)


def _date_field(label: str, value: datetime | date | None) -> SourceFieldOut | None:
    day = _day(value)
    return SourceFieldOut(label=label, on=day) if day else None


def _section(
    heading: str, *fields: SourceFieldOut | None, text: str | None = None
) -> SourceSectionOut | None:
    present = [f for f in fields if f is not None]
    if not present and not text:
        return None
    return SourceSectionOut(heading=heading, fields=present, text=text)


def _sections(*sections: SourceSectionOut | None) -> tuple[SourceSectionOut, ...]:
    return tuple(s for s in sections if s is not None)


def _matter(raw: RawMatter) -> _Readable:
    # Custom-field facts quote the field's value, so list every field as "name: value".
    fields = [f"{v.field_name}: {v.value}" for v in raw.custom_field_values]
    stage = raw.matter_stage.name if raw.matter_stage else None
    text = _lines(
        raw.description,
        f"Stage: {stage}" if stage else None,
        f"Status: {raw.status}" if raw.status else None,
        *fields,
    )
    sections = _sections(
        _section("Summary", text=raw.description),
        _section(
            "Matter",
            _field("Client", _name(raw.client)),
            _field("Practice area", _name(raw.practice_area)),
            _field("Stage", stage),
            _field("Status", raw.status),
            _field("Responsible attorney", _name(raw.responsible_attorney)),
            _date_field("Opened", raw.open_date),
            _date_field("Closed", raw.close_date),
        ),
        _section(
            "Case fields",
            *(_custom_field(v) for v in raw.custom_field_values if v.field_name),
        ),
    )
    return _Readable(raw.display_number, raw.open_date, None, text, sections)


def _task(task: RawTask) -> _Readable:
    sections = _sections(
        _section(
            "Task",
            _field("Status", _words(task.status)),
            _field("Priority", _words(task.priority)),
            _date_field("Due", task.due_at),
            _date_field("Completed", task.completed_at),
            _field("Assigned to", _name(task.assignee)),
            _field(
                "Statute of limitations", True if task.statute_of_limitations else None
            ),
        ),
        _section("Description", text=task.description),
    )
    text = _lines(task.name, task.description)
    return _Readable(task.name, _day(task.due_at), _name(task.assignee), text, sections)


def _readable(source: Source) -> _Readable:
    raw = source.raw_json
    match source.clio_type:
        case SourceType.MATTER:
            return _matter(RawMatter.model_validate(raw))
        case SourceType.NOTE:
            note = RawNote.model_validate(raw)
            return _Readable(note.subject, note.date, _name(note.author), note.detail)
        case SourceType.COMMUNICATION:
            email = RawCommunication.model_validate(raw)
            sender = email.senders[0].name if email.senders else None
            return _Readable(email.subject, email.date, sender, email.body)
        case SourceType.TASK:
            return _task(RawTask.model_validate(raw))
        case SourceType.CALENDAR_ENTRY:
            entry = RawCalendarEntry.model_validate(raw)
            text = _lines(entry.summary, entry.location, entry.description)
            return _Readable(entry.summary, _day(entry.start_at), None, text)
        case SourceType.ACTIVITY:
            activity = RawActivity.model_validate(raw)
            title = activity.note or activity.type
            return _Readable(title, activity.date, None, activity.note)
        case SourceType.DOCUMENT:
            document = RawDocument.model_validate(raw)
            return _Readable(document.name or document.filename, None, None, None)
        case SourceType.RELATIONSHIP:
            relationship = RawRelationship.model_validate(raw)
            contact = _name(relationship.contact)
            text = _lines(contact, relationship.description)
            return _Readable(relationship.description, None, None, text)
        case _:
            return _Readable(RawContact.model_validate(raw).name, None, None, None)


def source_out(session: Session, source: Source) -> SourceOut:
    readable = _readable(source)
    pages: list[PageRef] = []
    if source.clio_type is SourceType.DOCUMENT:
        rendered = session.scalars(
            select(Page)
            .where(Page.source_id == source.id, Page.image_path.is_not(None))
            .order_by(Page.page_no)
        )
        pages = [
            PageRef(
                page_id=p.id, page_no=p.page_no, image_url=f"/api/pages/{p.id}/image"
            )
            for p in rendered
        ]
    created = source.clio_created_at.date() if source.clio_created_at else None
    document_date = None
    if source.clio_type is SourceType.DOCUMENT:
        document_date = _day(RawDocument.model_validate(source.raw_json).received_at)
    return SourceOut(
        source_id=source.id,
        source_type=source.clio_type,
        title=readable.title,
        occurred_on=readable.occurred_on or created,
        author=readable.author,
        text=readable.text,
        pages=pages,
        sections=list(readable.sections),
        document_date=document_date,
    )


def fact_source(session: Session, fact_id: int) -> FactSourceOut:
    matter_id = session.scalar(select(Fact.matter_id).where(Fact.id == fact_id))
    fact = None
    if matter_id is not None:
        fact = session.scalars(
            renderable_facts(matter_id).where(Fact.id == fact_id)
        ).first()
    if fact is None:
        raise FactNotFound(f"fact {fact_id} does not exist or cannot be shown")
    payload = PAYLOAD_BY_KIND[fact.kind].model_validate(fact.value_json)
    corroborating = session.scalars(
        select(Source).where(
            Source.id.in_(payload.corroborating_source_ids),
            Source.id != fact.source_id,
            Source.matter_id == fact.matter_id,
        )
    )
    return FactSourceOut(
        fact=fact_out(fact),
        source=source_out(session, fact.source),
        corroborating=[source_out(session, s) for s in corroborating],
    )


def page_image_path(session: Session, page_id: int) -> Path:
    page = session.get(Page, page_id)
    if page is None or page.image_path is None:
        raise PageNotFound(f"page {page_id} has no rendered image")
    data_dir = get_settings().data_dir.resolve()
    path = (data_dir / page.image_path).resolve()
    # Stored paths are relative to DATA_DIR; refuse anything that resolves outside it.
    if not path.is_relative_to(data_dir) or not path.is_file():
        raise PageNotFound(f"page {page_id} image is missing")
    return path
