"""Notes and emails have a prompt of their own, apart from the custom-field record (D42).

The custom-field record is marked read by its request's cache key, which holds its
prompt's name and version, while a note or email is marked read by a hash of its own
content. With one shared prompt, a new version for notes made the next digest read the
custom fields again, and with them the facts behind the money tiles. Now a new note
prompt reaches only the records named for a re-read. Only `llm._execute` is faked.
"""

from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.digest import llm
from app.digest.reextract import mark_unread, select_units
from app.digest.run import run_digest
from app.models import Source, SourceType

MATTER = 42
FIELD = 420
FIELD_TEXT = "Invented field value"
NOTE_TEXT = "Invented note about an invented filing"


class FakeModel:
    """Answers every call; records which prompt read which source."""

    def __init__(self) -> None:
        self.reads: list[tuple[str, int | None, str]] = []

    def __call__(self, request: llm.ModelRequest) -> llm.ModelResult:
        if request.purpose == "map_fields":
            data: dict[str, Any] = {
                "fields": [{"field_id": FIELD, "slot": "none"}],
                "stage": None,
            }
        elif request.purpose == "extract_record":
            self.reads.append(
                (request.prompt.name, request.source_id, request.prompt.version)
            )
            data = {"document_type": "other", "facts": []}
        else:
            return llm.ModelResult(None, 0, 0, "not needed here")
        return llm.ModelResult(data, 1, 1)


@pytest.fixture
def model(data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> FakeModel:
    for name in ("EXTRACT_MODEL", "MERGE_MODEL"):
        monkeypatch.setenv(name, "invented")
    get_settings.cache_clear()
    fake = FakeModel()
    monkeypatch.setattr(llm, "_execute", fake)
    return fake


@pytest.fixture
def note(session: Session) -> Source:
    record = Source(
        matter_id=MATTER,
        clio_type=SourceType.NOTE,
        clio_id="n",
        raw_json={"id": 1, "subject": "Invented", "detail": NOTE_TEXT},
    )
    session.add_all(
        [
            record,
            Source(
                matter_id=MATTER,
                clio_type=SourceType.MATTER,
                clio_id=str(MATTER),
                raw_json={
                    "id": MATTER,
                    "custom_field_values": [
                        {
                            "custom_field": {"id": FIELD},
                            "field_name": "Field A",
                            "value": FIELD_TEXT,
                        }
                    ],
                },
            ),
            Source(
                matter_id=MATTER,
                clio_type=SourceType.CUSTOM_FIELD,
                clio_id=str(FIELD),
                raw_json={"id": FIELD, "name": "Field A"},
            ),
        ]
    )
    session.commit()
    return record


def _bump(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    """The prompt `name` as if its file had a new version line."""
    load = llm.load_prompt

    def bumped(prompt: str) -> llm.Prompt:
        found = load(prompt)
        if prompt != name:
            return found
        return llm.Prompt(name=found.name, version="next", text=found.text)

    monkeypatch.setattr(llm, "load_prompt", bumped)


def test_notes_and_custom_fields_are_read_with_their_own_prompts(
    model: FakeModel, session: Session, note: Source
) -> None:
    run_digest(session, MATTER)

    matter = session.scalars(
        select(Source).where(Source.clio_type == SourceType.MATTER)
    ).one()
    prompts = {source_id: prompt for prompt, source_id, _ in model.reads}
    assert prompts == {note.id: "extract_note", matter.id: "extract_record"}


def test_a_new_note_prompt_rereads_only_the_records_named(
    model: FakeModel,
    session: Session,
    note: Source,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_digest(session, MATTER)
    _bump(monkeypatch, "extract_note")
    model.reads.clear()

    run_digest(session, MATTER)
    assert model.reads == []  # a plain digest reads nothing again

    mark_unread(select_units(session, MATTER, records=[note.id]))
    session.commit()
    run_digest(session, MATTER)
    assert model.reads == [("extract_note", note.id, "next")]
