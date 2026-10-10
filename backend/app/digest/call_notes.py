"""Notes from one call's transcript: a summary, commitments, dates and amounts
mentioned, and follow-ups.

One cached, costed model call writes each note with a quote. Code does the rest: it
finds the quote in the transcript and records its offsets, reads the dates and amounts
in the quoted words, and drops a note whose quote is not in the transcript or whose own
text states a figure the quote does not. Backend calls this from its notes job and
stores the notes; nothing here writes to the database except the model-call log.
"""

import json
import logging
from collections import Counter
from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.digest import llm
from app.digest.llm import ModelsNotConfigured
from app.digest.records import QUOTE_LIMIT
from app.digest.verify import find_quote
from app.services.text_mentions import (
    AmountMention,
    DateMention,
    DatePrecision,
    find_amounts,
    find_dates,
)

log = logging.getLogger(__name__)

__all__ = [
    "CallNoteDraft",
    "CallNotes",
    "CallNotesFailed",
    "MentionedDate",
    "ModelsNotConfigured",
    "extract_call_notes",
]

CallNoteKind = Literal["summary", "commitment", "date", "amount", "follow_up"]
# Kinds whose point is the figure: with none in their own words, they take the quote's.
FIGURE_KINDS = {"date", "amount"}
HALF_YEAR_DAYS = 183


class CallNotesFailed(Exception):
    """The model call failed. Its failure is cached; ask again with `retry_failed`."""


class _ModelNote(BaseModel):
    kind: CallNoteKind
    text: str
    quote: str


class _ModelNotes(BaseModel):
    notes: list[_ModelNote]


class MentionedDate(BaseModel):
    on: date  # for a month, its first day
    precision: Literal["day", "month"]


class CallNoteDraft(BaseModel):
    """One note, ready to store. Field names follow `CallNoteOut` in the contract."""

    kind: CallNoteKind
    text: str
    quote: str  # the transcript's own words, transcript[quote_start:quote_end]
    quote_start: int
    quote_end: int
    amounts_cents: list[int]
    dates: list[MentionedDate]


@dataclass
class CallNotes:
    notes: list[CallNoteDraft]
    # Notes the model wrote that code did not keep, by reason. The job reports them.
    dropped: Counter[str] = field(default_factory=Counter)


def extract_call_notes(
    session: Session,
    transcript: str,
    *,
    matter_id: int,
    call_date: date | None = None,
    counterpart: str | None = None,
    retry_failed: bool = False,
) -> CallNotes:
    """Notes for one transcript. Raises `ModelsNotConfigured` when no model is set up,
    and `CallNotesFailed` when the model call failed."""
    if not transcript.strip():
        return CallNotes(notes=[])
    request = llm.ModelRequest(
        purpose="call_notes",
        role="extract",
        prompt=llm.load_prompt("call_notes"),
        user_text=_user_text(transcript, call_date, counterpart),
        output=_ModelNotes,
        matter_id=matter_id,
    )
    with llm.retrying_failed_calls() if retry_failed else nullcontext():
        result = llm.call(session, request)
    if not isinstance(result, _ModelNotes):
        raise CallNotesFailed("The call-notes model call failed; see llm_calls")
    notes = CallNotes(notes=[])
    for model_note in result.notes:
        draft, reason = _checked(model_note, transcript, call_date)
        if draft is None:
            notes.dropped[reason] += 1
        else:
            notes.notes.append(draft)
    log.info("Call notes: %d kept, dropped %s", len(notes.notes), dict(notes.dropped))
    return notes


def _user_text(transcript: str, call_date: date | None, counterpart: str | None) -> str:
    return json.dumps(
        {
            "call_with": counterpart,
            "call_date": call_date.isoformat() if call_date else None,
            "transcript": transcript,
        },
        indent=1,
    )


def _checked(
    note: _ModelNote, transcript: str, call_date: date | None
) -> tuple[CallNoteDraft | None, str]:
    span = find_quote(note.quote[:QUOTE_LIMIT], transcript)
    if span is None:
        return None, "quote_not_found"
    start, end = span
    quoted = transcript[start:end]
    said_amounts, said_dates = find_amounts(quoted), find_dates(quoted)
    note_amounts, note_dates = find_amounts(note.text), find_dates(note.text)
    amounts = [_supporting_amount(a, said_amounts) for a in note_amounts]
    dates = [_supporting_date(d, said_dates) for d in note_dates]
    if any(a is None for a in amounts) or any(d is None for d in dates):
        return None, "unsupported_figure"
    kept_amounts = [a for a in amounts if a is not None]
    kept_dates = [d for d in dates if d is not None]
    if note.kind in FIGURE_KINDS and not (note_amounts or note_dates):
        kept_amounts, kept_dates = said_amounts, said_dates
    draft = CallNoteDraft(
        kind=note.kind,
        text=note.text.strip(),
        quote=quoted,
        quote_start=start,
        quote_end=end,
        amounts_cents=list(dict.fromkeys(a.cents for a in kept_amounts)),
        dates=_resolved(kept_dates, call_date),
    )
    return draft, ""


def _supporting_amount(
    stated: AmountMention, said: list[AmountMention]
) -> AmountMention | None:
    """The amount in the quote that the note's amount restates, if any."""
    return next(
        (s for s in said if s.matches(stated.cents) or stated.matches(s.cents)), None
    )


def _supporting_date(
    stated: DateMention, said: list[DateMention]
) -> DateMention | None:
    """The date in the quote that the note's date restates. A note may say less than
    the quote ("March 3" for "March 3, 2031"), never more (a year the quote lacks)."""
    return next((s for s in said if stated.matches(s.on)), None)


def _resolved(
    mentions: list[DateMention], call_date: date | None
) -> list[MentionedDate]:
    """Dates as stored. A day said without a year is the nearest such day to the call;
    with no call date, it cannot be placed and is left out."""
    resolved: list[MentionedDate] = []
    for mention in mentions:
        if mention.precision is DatePrecision.DAY:
            resolved.append(MentionedDate(on=mention.on, precision="day"))
        elif mention.precision is DatePrecision.MONTH:
            resolved.append(MentionedDate(on=mention.on, precision="month"))
        elif call_date is not None:
            day = _nearest(mention.on.month, mention.on.day, call_date)
            if day is not None:
                resolved.append(MentionedDate(on=day, precision="day"))
    return list({(d.on, d.precision): d for d in resolved}.values())


def _nearest(month: int, day: int, around: date) -> date | None:
    candidates = []
    for year in (around.year - 1, around.year, around.year + 1):
        try:
            candidates.append(date(year, month, day))
        except ValueError:
            continue  # Feb 29 outside a leap year
    if not candidates:
        return None
    best = min(candidates, key=lambda d: abs((d - around).days))
    return best if abs((best - around).days) <= HALF_YEAR_DAYS else None
