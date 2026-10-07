"""The brief's headline cites the facts it rests on, checked like sentence citations."""

from pathlib import Path

import pytest
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.digest import llm
from app.digest.merge import Brief, BriefSentence, write_brief
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


def _fact(session: Session, source: Source, title: str) -> Fact:
    fact = Fact(
        matter_id=MATTER,
        kind=FactKind.TREATMENT_VISIT,
        title=title,
        value_json={},
        source_id=source.id,
        page_no=1,
        quote="Invented quote",
        confidence=Confidence.HIGH,
        origin=Origin.MODEL,
        significance=60,
    )
    session.add(fact)
    session.flush()
    return fact


def test_the_headline_keeps_only_citations_of_facts_that_exist(
    data_dir: Path, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = Source(
        matter_id=MATTER, clio_type=SourceType.DOCUMENT, clio_id="d", raw_json={}
    )
    session.add(source)
    session.flush()
    first = _fact(session, source, "Invented visit")
    second = _fact(session, source, "Another invented visit")

    def answer(
        _session: Session, requests: list[llm.ModelRequest]
    ) -> list[BaseModel | None]:
        return [
            Brief(
                headline="Invented headline",
                headline_fact_ids=[first.id, UNKNOWN_ID],
                stage="treating",
                stage_fact_ids=[],
                sentences=[BriefSentence(text="Invented.", fact_ids=[second.id])],
            )
            for _ in requests
        ]

    monkeypatch.setenv("MERGE_MODEL", "invented-merge")
    get_settings.cache_clear()
    monkeypatch.setattr(llm, "run_batch", answer)
    assert write_brief(session, MATTER)

    brief = session.scalars(select(Digest).where(Digest.kind == DigestKind.BRIEF)).one()
    assert brief.content_json["headline_fact_ids"] == [first.id]


def test_the_brief_prompt_asks_for_the_headline_citations() -> None:
    assert "headline_fact_ids" in llm.load_prompt("brief").text
