"""Notes from a call transcript: every note quotes the transcript, and code places the
quote and reads the dates and amounts in it.

Only the model API is faked (`llm._execute`); the cache in `llm.py` is real.
"""

from datetime import date
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.digest import llm
from app.digest.call_notes import (
    CallNotesFailed,
    MentionedDate,
    extract_call_notes,
)

MATTER = 40
CALL_DAY = date(2031, 2, 20)
TRANSCRIPT = (
    "Hi, this is the firm calling about the invented claim. "
    "The adjuster said they would offer $850 to settle the property part. "
    "She will send the written offer by March 3rd. "
    "I told her we still need the clinic records before we respond. "
    "We agreed to talk again on April 10, 2031."
)


def _note(kind: str, text: str, quote: str) -> dict[str, str]:
    return {"kind": kind, "text": text, "quote": quote}


ANSWER = {
    "notes": [
        _note(
            "summary",
            "The adjuster made an offer and set out next steps.",
            "The adjuster said they would offer $850",
        ),
        _note(
            "amount",
            "The adjuster will offer $850 for the property part.",
            "they would offer $850 to settle the property part",
        ),
        _note(
            "commitment",
            "The adjuster will send the written offer by March 3.",
            "She will send the written offer by March 3rd.",
        ),
        _note(
            "date",
            "Next call on April 10, 2031.",
            "We agreed to talk again on April 10, 2031.",
        ),
        _note(
            "follow_up",
            "Get the clinic records before responding.",
            "WE STILL NEED THE CLINIC RECORDS",
        ),
        # Not in the transcript at all.
        _note("commitment", "The client agreed to surgery.", "the client agreed"),
        # Its quote is real, but its figure is not the quote's.
        _note("amount", "The offer is $900.", "they would offer $850"),
    ]
}


class FakeModel:
    def __init__(self, answer: dict[str, Any] | None) -> None:
        self.answer = answer
        self.calls = 0

    def __call__(self, request: llm.ModelRequest) -> llm.ModelResult:
        self.calls += 1
        if self.answer is None:
            return llm.ModelResult(None, 1, 0, "ExtractionFailed: invented failure")
        return llm.ModelResult(self.answer, 1, 1)


@pytest.fixture
def model(data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> FakeModel:
    monkeypatch.setenv("EXTRACT_MODEL", "invented-extract")
    get_settings.cache_clear()
    fake = FakeModel(ANSWER)
    monkeypatch.setattr(llm, "_execute", fake)
    return fake


def _notes(session: Session) -> Any:
    return extract_call_notes(
        session,
        TRANSCRIPT,
        matter_id=MATTER,
        call_date=CALL_DAY,
        counterpart="Invented adjuster (insurer)",
    )


def test_each_note_points_at_its_quote_in_the_transcript(
    model: FakeModel, session: Session
) -> None:
    result = _notes(session)

    assert [n.kind for n in result.notes] == [
        "summary",
        "amount",
        "commitment",
        "date",
        "follow_up",
    ]
    for note in result.notes:
        assert TRANSCRIPT[note.quote_start : note.quote_end] == note.quote
    follow_up = result.notes[4]
    assert follow_up.quote == "we still need the clinic records"


def test_a_note_whose_quote_is_not_in_the_transcript_is_dropped_and_counted(
    model: FakeModel, session: Session
) -> None:
    result = _notes(session)

    assert all("surgery" not in n.text for n in result.notes)
    assert result.dropped["quote_not_found"] == 1


def test_a_note_stating_a_figure_its_quote_does_not_is_dropped(
    model: FakeModel, session: Session
) -> None:
    result = _notes(session)

    assert all("$900" not in n.text for n in result.notes)
    assert result.dropped["unsupported_figure"] == 1


def test_amounts_and_dates_are_read_from_the_quote_by_code(
    model: FakeModel, session: Session
) -> None:
    summary, amount, commitment, when, follow_up = _notes(session).notes

    assert amount.amounts_cents == [85000]
    assert when.dates == [MentionedDate(on=date(2031, 4, 10), precision="day")]
    # Said without a year: the nearest such day to the call.
    assert commitment.dates == [MentionedDate(on=date(2031, 3, 3), precision="day")]
    # A note whose own words state no figure carries none.
    assert summary.amounts_cents == [] and follow_up.dates == []


def test_a_second_call_on_the_same_transcript_is_answered_from_the_cache(
    model: FakeModel, session: Session
) -> None:
    first = _notes(session)
    second = _notes(session)

    assert model.calls == 1
    assert second.notes == first.notes


def test_without_a_model_it_raises_models_not_configured(
    data_dir: Path, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Built without the .env file, so model settings there cannot leak in.
    bare = Settings(_env_file=None)  # type: ignore[call-arg]
    monkeypatch.setattr(llm, "get_settings", lambda: bare)
    fake = FakeModel(ANSWER)
    monkeypatch.setattr(llm, "_execute", fake)

    with pytest.raises(llm.ModelsNotConfigured):
        _notes(session)
    assert fake.calls == 0


def test_a_failed_call_raises_call_notes_failed(
    model: FakeModel, session: Session
) -> None:
    model.answer = None
    with pytest.raises(CallNotesFailed):
        _notes(session)


def test_an_empty_transcript_needs_no_model(model: FakeModel, session: Session) -> None:
    result = extract_call_notes(session, "  ", matter_id=MATTER)

    assert result.notes == [] and model.calls == 0


# D28: one amount reader serves the draft checker and the call notes, so a figure said
# in any form it reads is checked, and parsed, the same way in both.
SPOKEN_AMOUNTS = [
    ("They will pay twelve grand for it.", "They will pay $12,000.", 1_200_000),
    (
        "Lost wages come to about 12k so far.",
        "Lost wages are about $12,000.",
        1_200_000,
    ),
    ("The bill came to 500 bucks.", "The bill was $500.", 50_000),
    ("She said 850$ was the copay.", "The copay is $850.", 85_000),
    # A full-width dollar sign, and a narrow no-break space between thousands.
    ("The deposit is \uff04850 today.", "The deposit is $850.", 85_000),
    ("The scan was 2\u202f000 dollars.", "The scan cost $2,000.", 200_000),
]


def _one_note(
    model: FakeModel, session: Session, transcript: str, kind: str, text: str
) -> Any:
    model.answer = {"notes": [_note(kind, text, transcript)]}
    return extract_call_notes(session, transcript, matter_id=MATTER)


@pytest.mark.parametrize(("said", "noted", "cents"), SPOKEN_AMOUNTS)
def test_an_amount_said_in_any_form_supports_a_note_that_restates_it(
    model: FakeModel, session: Session, said: str, noted: str, cents: int
) -> None:
    result = _one_note(model, session, said, "amount", noted)

    assert [n.amounts_cents for n in result.notes] == [[cents]]
    assert not result.dropped


@pytest.mark.parametrize(("said", "_noted", "cents"), SPOKEN_AMOUNTS)
def test_an_amount_note_without_a_figure_takes_the_spoken_one(
    model: FakeModel, session: Session, said: str, _noted: str, cents: int
) -> None:
    result = _one_note(model, session, said, "amount", "An amount was agreed.")

    assert [n.amounts_cents for n in result.notes] == [[cents]]


def test_a_note_stating_another_figure_than_the_spoken_one_is_dropped(
    model: FakeModel, session: Session
) -> None:
    said = "They will pay twelve grand for it."
    result = _one_note(model, session, said, "amount", "They will pay $15,000.")

    assert result.notes == []
    assert result.dropped["unsupported_figure"] == 1
