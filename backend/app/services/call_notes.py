"""A call's notes, written in the background from its transcript.

Pipeline's `extract_call_notes` reads the transcript with the model and returns notes,
each quoting a span of it. This job makes the transcript a `call` source, checks each
note's span against it once more, and stores the notes as `call_note` facts on that
source, so their chips open the transcript with the quote highlighted. Call notes are
internal: no share setting releases the kind (default-deny).
"""

import logging
import threading
from collections.abc import Callable
from typing import Any, Protocol

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import get_sessionmaker
from app.models import (
    Call,
    Confidence,
    Fact,
    FactKind,
    NotesStatus,
    Origin,
    Source,
    SourceType,
)
from app.schemas import CallNoteDate, validate_payload
from app.services.visibility import fact_visibility

log = logging.getLogger(__name__)

# Same bound as the run rows' `error` column.
MAX_ERROR_CHARS = 2000
# Where a note ranks among the matter's facts. A commitment or a follow-up is something
# someone now has to do, so it outranks a summary.
SIGNIFICANCE_BY_KIND = {
    "commitment": 80,
    "follow_up": 75,
    "summary": 70,
    "date": 65,
    "amount": 65,
}


class NoteDraft(Protocol):
    """One note as `extract_call_notes` returns it."""

    kind: str
    text: str
    quote: str
    quote_start: int
    quote_end: int
    amounts_cents: list[int]
    dates: list[Any]


Extractor = Callable[..., Any]


def start(call_id: int) -> None:
    """Write the call's notes in a background thread with its own session."""

    def target() -> None:
        try:
            with get_sessionmaker()() as session:
                try:
                    extract = _extractor()
                except ImportError as error:
                    _fail(session, call_id, f"Call notes are not available: {error}")
                    return
                write_notes(session, call_id, extract)
        except Exception:
            log.exception("Call %d: the notes job could not run", call_id)

    threading.Thread(target=target, daemon=True).start()


def write_notes(session: Session, call_id: int, extract: Extractor) -> None:
    """Run the extractor on the call's transcript and store its notes; record the outcome."""
    from app.digest.llm import ModelsNotConfigured

    call = session.get(Call, call_id)
    if call is None:
        return
    try:
        result = extract(
            session,
            call.transcript,
            matter_id=call.matter_id,
            call_date=call.started_at.date(),
            counterpart=call.target_json.get("name") or call.target_json.get("role"),
        )
    except ModelsNotConfigured:
        session.rollback()
        call.notes_status = NotesStatus.NO_MODEL
    except Exception as error:
        log.exception("Call %d: notes failed", call_id)
        session.rollback()
        _fail(session, call_id, str(error) or type(error).__name__)
        return
    else:
        stored = _store(session, call, list(result.notes))
        call.notes_status = NotesStatus.DONE
        log.info(
            "Call %d: %d notes stored, %d dropped", call_id, stored, len(result.dropped)
        )
    session.commit()


def _fail(session: Session, call_id: int, error: str) -> None:
    call = session.get(Call, call_id)
    if call is not None:
        call.notes_status = NotesStatus.FAILED
        call.notes_error = error[:MAX_ERROR_CHARS]
        session.commit()


def _store(session: Session, call: Call, drafts: list[NoteDraft]) -> int:
    source = _transcript_source(session, call)
    session.execute(
        delete(Fact).where(Fact.source_id == source.id, Fact.kind == FactKind.CALL_NOTE)
    )
    provider = None
    if call.target_json.get("role") == "provider":
        provider = _contact_id(call.target_json.get("target_id"))
    stored = 0
    for draft in drafts:
        # The notes cite the transcript: a span that does not hold its quote is dropped.
        if call.transcript[draft.quote_start : draft.quote_end] != draft.quote:
            log.warning(
                "Call %d: a note's span does not hold its quote; dropped", call.id
            )
            continue
        session.add(
            Fact(
                matter_id=call.matter_id,
                kind=FactKind.CALL_NOTE,
                title=draft.text,
                value_json=validate_payload(
                    FactKind.CALL_NOTE,
                    {
                        "note_kind": draft.kind,
                        "quote_start": draft.quote_start,
                        "quote_end": draft.quote_end,
                        "amounts_cents": list(draft.amounts_cents),
                        "dates": [
                            CallNoteDate.model_validate(
                                d, from_attributes=True
                            ).model_dump(mode="json")
                            for d in draft.dates
                        ],
                    },
                ),
                event_date=call.started_at.date(),
                source_id=source.id,
                quote=draft.quote,
                provider_contact_id=provider,
                visibility=fact_visibility(FactKind.CALL_NOTE, mentions_strategy=False),
                significance=SIGNIFICANCE_BY_KIND.get(draft.kind, 60),
                confidence=Confidence.MEDIUM,
                verified=True,
                origin=Origin.MODEL,
            )
        )
        stored += 1
    return stored


def _transcript_source(session: Session, call: Call) -> Source:
    """The call as a source, holding the transcript its notes quote."""
    raw = {
        "call_id": call.id,
        "name": call.target_json.get("name"),
        "role": call.target_json.get("role"),
        "started_at": call.started_at.isoformat(),
        "ended_at": call.ended_at.isoformat() if call.ended_at else None,
        "transcript": call.transcript,
    }
    source = session.get(Source, call.source_id) if call.source_id else None
    if source is None:
        source = session.scalars(
            select(Source).where(
                Source.matter_id == call.matter_id,
                Source.clio_type == SourceType.CALL,
                Source.clio_id == f"call-{call.id}",
            )
        ).first()
    if source is None:
        source = Source(
            matter_id=call.matter_id,
            clio_type=SourceType.CALL,
            clio_id=f"call-{call.id}",
            raw_json=raw,
            clio_created_at=call.started_at,
        )
        session.add(source)
    source.raw_json = raw
    source.clio_updated_at = call.ended_at
    session.flush()
    call.source_id = source.id
    return source


def _contact_id(target_id: object) -> int | None:
    if isinstance(target_id, str) and target_id.startswith("contact:"):
        try:
            return int(target_id.removeprefix("contact:"))
        except ValueError:
            return None
    return None


def _extractor() -> Extractor:
    """Pipeline's notes extractor (C-P), imported when a job runs."""
    from app.digest.call_notes import extract_call_notes

    return extract_call_notes
