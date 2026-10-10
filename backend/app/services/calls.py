"""Calls placed from Clarity: start with consent, save the transcript, end, read back.

Everything here lives in Clarity's own tables; nothing is written to Clio (rule 1). A
call cannot start without the attorney confirming consent, and the wording confirmed is
stored with it. Ending a call starts its notes in the background (`call_notes.py`), so
no request waits on a model (rule 5).
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Call, Fact, FactKind, NotesStatus
from app.schemas import (
    CallDetailOut,
    CallNoteOut,
    CallNotePayload,
    CallOut,
    CallTargetOut,
)
from app.services import call_notes
from app.services.call_targets import target_for
from app.services.fact_views import fact_ref, renderable_facts


class CallNotFound(LookupError):
    pass


class ConsentRequired(ValueError):
    """A call may not start until the attorney confirms consent (D8)."""


class TranscriptClosed(ValueError):
    """The notes have been written from this transcript, so it no longer changes."""


def start_call(
    session: Session,
    matter_id: int,
    target_id: str,
    consent_confirmed: bool,
    consent_text: str,
    now: datetime,
) -> CallOut:
    if not consent_confirmed:
        raise ConsentRequired("confirm consent before the call starts")
    target = target_for(session, matter_id, target_id, now.date())
    call = Call(
        matter_id=matter_id,
        target_json=target.model_dump(mode="json"),
        consent_text=consent_text,
        started_at=now,
    )
    session.add(call)
    session.commit()
    return call_out(call)


def save_transcript(session: Session, call_id: int, text: str, final: bool) -> CallOut:
    call = get_call(session, call_id)
    if call.notes_status in (NotesStatus.RUNNING, NotesStatus.DONE):
        raise TranscriptClosed(f"call {call_id} already has notes from its transcript")
    call.transcript = text
    call.transcript_final = call.transcript_final or final
    session.commit()
    return call_out(call)


def end_call(session: Session, call_id: int, now: datetime) -> CallOut:
    """End the call and start its notes. Ending again only retries notes that failed."""
    call = get_call(session, call_id)
    call.ended_at = call.ended_at or now
    if call.notes_status in (NotesStatus.RUNNING, NotesStatus.DONE):
        session.commit()
        return call_out(call)
    if not get_settings().models_configured:
        call.notes_status = NotesStatus.NO_MODEL
        session.commit()
        return call_out(call)
    call.notes_status = NotesStatus.RUNNING
    call.notes_error = None
    session.commit()
    call_notes.start(call.id)
    return call_out(call)


def list_calls(session: Session, matter_id: int) -> list[CallOut]:
    calls = session.scalars(
        select(Call)
        .where(Call.matter_id == matter_id)
        .order_by(Call.started_at.desc(), Call.id.desc())
    )
    return [call_out(c) for c in calls]


def call_detail(session: Session, call_id: int) -> CallDetailOut:
    call = get_call(session, call_id)
    notes: list[CallNoteOut] = []
    if call.source_id is not None:
        facts = session.scalars(
            renderable_facts(call.matter_id).where(
                Fact.source_id == call.source_id, Fact.kind == FactKind.CALL_NOTE
            )
        )
        for fact in facts:
            payload = CallNotePayload.model_validate(fact.value_json)
            if (
                payload.note_kind is None
                or payload.quote_start is None
                or payload.quote_end is None
            ):
                continue
            notes.append(
                CallNoteOut(
                    fact=fact_ref(fact),
                    kind=payload.note_kind,
                    text=fact.title,
                    quote_start=payload.quote_start,
                    quote_end=payload.quote_end,
                )
            )
    notes.sort(key=lambda n: (n.quote_start, n.fact.id))
    return CallDetailOut(call=call_out(call), transcript=call.transcript, notes=notes)


def get_call(session: Session, call_id: int) -> Call:
    call = session.get(Call, call_id)
    if call is None:
        raise CallNotFound(f"call {call_id} does not exist")
    return call


def call_out(call: Call) -> CallOut:
    return CallOut(
        call_id=call.id,
        target=CallTargetOut.model_validate(call.target_json),
        started_at=call.started_at,
        ended_at=call.ended_at,
        consent_text=call.consent_text,
        notes_status=call.notes_status.value,
    )
