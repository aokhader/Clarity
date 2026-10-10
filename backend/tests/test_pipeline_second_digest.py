"""A second digest over unchanged inputs makes no model calls.

Only the model API is faked (`llm._execute`); the cache in `llm.py` is real. Three
things used to send a second digest back to the model: a call that had failed was
asked again, facts the scorer left out of a batch were scored again in a new batch,
and the custom-field record was re-applied on every run, re-creating the fact dedup
had removed, whose new id then missed the scoring and brief caches.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.config import get_settings
from app.digest import llm
from app.digest.run import run_digest
from app.models import Page, Source, SourceType

MATTER = 20
FIELD = 400
FIELD_TEXT = "Invented charge of 100 dollars"
PAGE_TEXT = "Invented visit at an invented clinic"


class FakeModel:
    """Answers by purpose and counts every call that would have reached the model."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, request: llm.ModelRequest) -> llm.ModelResult:
        self.calls.append(request.purpose)
        data = self.answer(request)
        if data is None:
            return llm.ModelResult(None, 10, 0, "ExtractionFailed: invented failure")
        return llm.ModelResult(data, 10, 5)

    def answer(self, request: llm.ModelRequest) -> dict[str, Any] | None:
        if request.purpose == "map_fields":
            return {"fields": [{"field_id": FIELD, "slot": "none"}], "stage": None}
        if request.purpose == "extract_page":
            visit = {
                "kind": "treatment_visit",
                "title": "Invented visit",
                "event_date": "2020-03-03",
                "quote": PAGE_TEXT,
            }
            return {"document_type": "medical_record", "facts": [visit]}
        if request.purpose == "extract_record":
            if FIELD_TEXT not in request.user_text:
                return None  # the note's extraction always fails
            bill = {
                "kind": "medical_bill",
                "title": "Invented charge",
                "event_date": "2020-03-01",
                "amount": 100,
                "quote": FIELD_TEXT,
            }
            # The same bill twice from one record: dedup keeps one.
            return {"document_type": "intake", "facts": [bill, dict(bill)]}
        if request.purpose == "significance":
            ids = [row["fact_id"] for row in json.loads(request.user_text)["facts"]]
            # The scorer always leaves the last fact of a batch out.
            return {"scores": [{"fact_id": i, "significance": 50} for i in ids[:-1]]}
        if request.purpose == "brief":
            ids = [row["fact_id"] for row in json.loads(request.user_text)["facts"]]
            return {
                "headline": "Invented headline",
                "headline_fact_ids": ids[:1],
                "stage": "intake",
                "stage_fact_ids": [],
                "sentences": [{"text": "Invented sentence.", "fact_ids": ids[:1]}],
                "open_questions": [],
            }
        return None


@pytest.fixture
def model(data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> FakeModel:
    for name, value in {
        "EXTRACT_MODEL": "invented-extract",
        "MERGE_MODEL": "invented-merge",
        "EXTRACT_PRICE_IN": "1",
        "EXTRACT_PRICE_OUT": "1",
        "MERGE_PRICE_IN": "1",
        "MERGE_PRICE_OUT": "1",
    }.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    fake = FakeModel()
    monkeypatch.setattr(llm, "_execute", fake)
    return fake


@pytest.fixture
def matter(session: Session) -> Session:
    # Pages are extracted after records, so on a real matter the custom-field facts
    # are not the newest; SQLite would otherwise hand a re-created fact its old id.
    document = Source(
        matter_id=MATTER, clio_type=SourceType.DOCUMENT, clio_id="40", raw_json={}
    )
    document.pages = [
        Page(page_no=1, has_text_layer=True, text=PAGE_TEXT, content_hash="p1")
    ]
    session.add(document)
    session.add_all(
        [
            Source(
                matter_id=MATTER,
                clio_type=SourceType.MATTER,
                clio_id=str(MATTER),
                raw_json={
                    "id": MATTER,
                    "custom_field_values": [
                        {
                            "custom_field": {"id": FIELD},
                            "field_name": "Field B",
                            "value": FIELD_TEXT,
                        }
                    ],
                },
            ),
            Source(
                matter_id=MATTER,
                clio_type=SourceType.CUSTOM_FIELD,
                clio_id=str(FIELD),
                raw_json={"id": FIELD, "name": "Field B"},
            ),
            Source(
                matter_id=MATTER,
                clio_type=SourceType.NOTE,
                clio_id="30",
                raw_json={
                    "id": 30,
                    "subject": "Invented note",
                    "detail": "An invented note the model cannot read.",
                    "date": "2020-03-02",
                },
            ),
        ]
    )
    session.commit()
    return session


def test_a_second_digest_over_unchanged_inputs_makes_no_model_calls(
    model: FakeModel, matter: Session
) -> None:
    run_digest(matter, MATTER)
    assert {"map_fields", "extract_record", "significance", "brief"} <= set(model.calls)

    model.calls.clear()
    second = run_digest(matter, MATTER)

    assert model.calls == []
    # The note it could not read is still missing, and the run says so.
    assert second.error is not None and "failed" in second.error


def test_a_failed_call_is_asked_again_when_asked_to(
    model: FakeModel, matter: Session
) -> None:
    run_digest(matter, MATTER)
    model.calls.clear()

    run_digest(matter, MATTER, retry_failed=True)

    assert model.calls == ["extract_record"]
