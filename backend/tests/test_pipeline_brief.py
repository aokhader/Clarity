"""The brief: what its model is given, and what is kept of its answer.

The headline cites the facts it rests on, checked like sentence citations. The input
carries every computed total with the facts it adds up, names each fact's source, and
writes money and dates the one way the brief should, so the model copies rather than
converts. A new prompt version writes the brief again even when the facts are unchanged.
"""

import json
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.digest import llm
from app.digest.brief import Brief, BriefSentence, brief_payload, write_brief
from app.models import (
    Confidence,
    Digest,
    DigestKind,
    Fact,
    FactKind,
    Origin,
    Source,
    SourceType,
)

MATTER = 5
UNKNOWN_ID = 9999
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _source(session: Session, kind: SourceType, raw: dict[str, Any]) -> Source:
    source = Source(
        matter_id=MATTER,
        clio_type=kind,
        clio_id=str(len(raw)) + kind.value,
        raw_json=raw,
    )
    session.add(source)
    session.flush()
    return source


def _fact(
    session: Session,
    source: Source,
    kind: FactKind = FactKind.TREATMENT_VISIT,
    **values: Any,
) -> Fact:
    fields: dict[str, Any] = {
        "title": "Invented fact",
        "value_json": {},
        "quote": "Invented quote",
        "confidence": Confidence.HIGH,
        "origin": Origin.MODEL,
        "significance": 60,
    }
    fact = Fact(matter_id=MATTER, kind=kind, source_id=source.id, **(fields | values))
    session.add(fact)
    session.flush()
    return fact


def _answer_with(brief: Brief, monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Answer every brief request with `brief`; returns a list that counts the calls."""
    calls: list[int] = []

    def answer(
        _session: Session, requests: list[llm.ModelRequest]
    ) -> list[BaseModel | None]:
        calls.extend(1 for _ in requests)
        return [brief for _ in requests]

    monkeypatch.setenv("MERGE_MODEL", "invented-merge")
    get_settings.cache_clear()
    monkeypatch.setattr(llm, "run_batch", answer)
    return calls


def _brief(headline_ids: list[int], sentence_ids: list[int]) -> Brief:
    return Brief(
        headline="Invented headline",
        headline_fact_ids=headline_ids,
        stage="treating",
        stage_fact_ids=[],
        sentences=[BriefSentence(text="Invented.", fact_ids=sentence_ids)],
    )


def test_the_headline_keeps_only_citations_of_facts_that_exist(
    data_dir: Path, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = _source(session, SourceType.DOCUMENT, {})
    first = _fact(session, document, page_no=1)
    second = _fact(session, document, page_no=1)
    _answer_with(_brief([first.id, UNKNOWN_ID], [second.id]), monkeypatch)

    assert write_brief(session, MATTER)

    brief = session.scalars(select(Digest).where(Digest.kind == DigestKind.BRIEF)).one()
    assert brief.content_json["headline_fact_ids"] == [first.id]


def test_the_brief_prompt_asks_for_the_headline_citations() -> None:
    assert "headline_fact_ids" in llm.load_prompt("brief").text


def test_totals_reach_the_model_with_the_facts_they_add_up(
    data_dir: Path, session: Session
) -> None:
    bill = _source(session, SourceType.DOCUMENT, {"name": "Invented bill"})
    first = _fact(
        session,
        bill,
        FactKind.MEDICAL_BILL,
        value_json={"amount_cents": 12050},
        provider_contact_id=60,
        page_no=2,
    )
    second = _fact(
        session,
        bill,
        FactKind.MEDICAL_BILL,
        value_json={"amount_cents": 30000},
        provider_contact_id=61,
        page_no=3,
    )
    ledger = _source(session, SourceType.ACTIVITY, {"type": "ExpenseEntry"})
    cost = _fact(
        session,
        ledger,
        FactKind.EXPENSE,
        value_json={"amount_cents": 5000},
        origin=Origin.CODE,
    )

    figures = brief_payload(session, MATTER)["key_figures"]

    assert figures["medical_bills_total"] == {
        "amount": "$420.50",
        "fact_ids": [first.id, second.id],
    }
    assert figures["firm_spend_total"] == {"amount": "$50.00", "fact_ids": [cost.id]}


def test_each_row_names_its_source_and_writes_money_and_dates_one_way(
    data_dir: Path, session: Session
) -> None:
    bill = _source(session, SourceType.DOCUMENT, {"name": "Invented bill"})
    note = _source(
        session, SourceType.NOTE, {"subject": "Invented call log", "date": "2020-04-02"}
    )
    ledger = _source(
        session,
        SourceType.ACTIVITY,
        {"type": "ExpenseEntry", "note": "Raw ledger words"},
    )
    on_page = _fact(
        session,
        bill,
        FactKind.MEDICAL_BILL,
        value_json={"amount_cents": 12050},
        event_date=date(2020, 3, 1),
        page_no=2,
    )
    in_note = _fact(
        session,
        note,
        FactKind.DEADLINE,
        value_json={"due_at": "2020-05-06T09:00:00"},
    )
    cost = _fact(
        session,
        ledger,
        FactKind.EXPENSE,
        value_json={"amount_cents": 5000},
        origin=Origin.CODE,
    )

    payload = brief_payload(session, MATTER)
    rows = {row["fact_id"]: row for row in payload["facts"]}

    assert rows[on_page.id]["date"] == "Mar 1, 2020"
    assert rows[on_page.id]["value"] == {"amount": "$120.50"}
    assert rows[on_page.id]["source"] == "Invented bill, page 2"
    assert rows[in_note.id]["source"] == "Invented call log, Apr 2, 2020"
    assert rows[in_note.id]["value"] == {"due_at": "May 6, 2020"}
    assert "Raw ledger words" not in rows[cost.id]["source"]
    text = json.dumps(payload)
    assert "_cents" not in text
    assert not ISO_DATE.search(text)


def test_the_matters_own_fields_reach_the_model_however_they_rank(
    data_dir: Path, session: Session
) -> None:
    matter = _source(session, SourceType.MATTER, {"id": MATTER})
    document = _source(session, SourceType.DOCUMENT, {"name": "Invented record"})
    for _ in range(60):
        _fact(session, document, page_no=1, significance=90)
    incident = _fact(
        session, matter, FactKind.INCIDENT, origin=Origin.CODE, significance=1
    )

    rows = brief_payload(session, MATTER)["facts"]

    assert incident.id in {row["fact_id"] for row in rows}


def test_the_prompt_forbids_questions_the_input_answers() -> None:
    assert "already answers" in llm.load_prompt("brief").text


def test_a_new_brief_prompt_writes_the_brief_again(
    data_dir: Path, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = _source(session, SourceType.DOCUMENT, {"name": "Invented record"})
    fact = _fact(session, document, page_no=1)
    calls = _answer_with(_brief([fact.id], [fact.id]), monkeypatch)
    assert write_brief(session, MATTER)
    assert not write_brief(session, MATTER)

    current = llm.load_prompt("brief")
    newer = llm.Prompt(
        name=current.name, version=f"{current.version}.1", text=current.text
    )
    monkeypatch.setattr(llm, "load_prompt", lambda _name: newer)

    assert write_brief(session, MATTER)
    assert len(calls) == 2


def test_a_rewritten_brief_says_when_it_was_written(
    data_dir: Path, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = _source(session, SourceType.DOCUMENT, {"name": "Invented record"})
    fact = _fact(session, document, page_no=1)
    _answer_with(_brief([fact.id], [fact.id]), monkeypatch)
    assert write_brief(session, MATTER)
    stored = session.scalars(
        select(Digest).where(Digest.kind == DigestKind.BRIEF)
    ).one()
    long_ago = datetime(2020, 1, 1, tzinfo=UTC)
    stored.created_at = long_ago
    session.commit()

    current = llm.load_prompt("brief")
    newer = llm.Prompt(
        name=current.name, version=f"{current.version}.1", text=current.text
    )
    monkeypatch.setattr(llm, "load_prompt", lambda _name: newer)
    assert write_brief(session, MATTER)
    session.commit()

    session.expire_all()
    rewritten = session.scalars(
        select(Digest).where(Digest.kind == DigestKind.BRIEF)
    ).one()
    assert rewritten.created_at > long_ago
