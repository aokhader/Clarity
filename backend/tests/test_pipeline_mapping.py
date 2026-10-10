"""A failed mapping call keeps the previous mapping and its facts, and says so.

The run used to carry on with empty roles and slots: it replaced the KPI and stage
facts with the stage alone, turned every medical charge into a firm cost, dropped
every provider, and stored that empty mapping over the good one.
"""

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.digest import llm
from app.digest.ledger import LedgerEntry, LedgerMapping
from app.digest.mapping import (
    FieldEntry,
    FieldMapping,
    RoleEntry,
    RoleMapping,
    build_mapping,
)
from app.digest.run import run_digest
from app.models import Fact, Origin, Source, SourceType

MATTER = 10
PROVIDER = 60
FIELD = 300

Answer = Callable[[llm.ModelRequest], BaseModel | None]


def _source(session: Session, kind: SourceType, clio_id: int, raw: dict) -> Source:
    source = Source(
        matter_id=MATTER, clio_type=kind, clio_id=str(clio_id), raw_json=raw
    )
    session.add(source)
    session.flush()
    return source


@pytest.fixture
def matter(session: Session) -> Session:
    _source(
        session,
        SourceType.MATTER,
        MATTER,
        {
            "id": MATTER,
            "status": "Open",
            "matter_stage": {"name": "Invented stage"},
            "client": {"id": 50, "name": "Invented Client"},
            "custom_field_values": [
                {
                    "custom_field": {"id": FIELD},
                    "field_name": "Field A",
                    "value": "$900",
                }
            ],
        },
    )
    _source(session, SourceType.CUSTOM_FIELD, FIELD, {"id": FIELD, "name": "Field A"})
    _source(
        session,
        SourceType.RELATIONSHIP,
        70,
        {
            "id": 70,
            "description": "Invented role",
            "contact": {"id": PROVIDER, "name": "Invented Clinic"},
        },
    )
    _source(
        session,
        SourceType.ACTIVITY,
        80,
        {"id": 80, "type": "ExpenseEntry", "date": "2020-02-01", "total": 120.0},
    )
    session.commit()
    return session


def _answers(request: llm.ModelRequest) -> BaseModel | None:
    if request.purpose == "map_roles":
        return RoleMapping(
            contacts=[RoleEntry(contact_id=PROVIDER, role="medical_provider")]
        )
    if request.purpose == "map_fields":
        return FieldMapping(
            fields=[FieldEntry(field_id=FIELD, slot="case_value")], stage="treating"
        )
    if request.purpose == "classify_activities":
        entries = json.loads(request.user_text)["entries"]
        return LedgerMapping(
            activities=[
                LedgerEntry(
                    activity_id=e["activity_id"],
                    is_medical_charge=True,
                    provider_contact_id=PROVIDER,
                )
                for e in entries
            ]
        )
    return None


def _failures(_request: llm.ModelRequest) -> BaseModel | None:
    return None


def _fake_model(monkeypatch: pytest.MonkeyPatch, answer: Answer) -> None:
    def run_batch(
        _session: Session, requests: list[llm.ModelRequest]
    ) -> list[BaseModel | None]:
        return [answer(r) for r in requests]

    monkeypatch.setattr(llm, "run_batch", run_batch)


def _code_facts(session: Session) -> list[tuple]:
    session.expire_all()
    facts = session.scalars(select(Fact).where(Fact.origin == Origin.CODE)).all()
    return sorted(
        (
            f.source_id,
            f.kind.value,
            json.dumps(f.value_json, sort_keys=True),
            f.provider_contact_id,
        )
        for f in facts
    )


def test_failed_mapping_calls_keep_the_previous_facts_and_providers(
    data_dir: Path, matter: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_model(monkeypatch, _answers)
    build_mapping(matter, MATTER)
    before = _code_facts(matter)
    kinds = {kind for _s, kind, _v, _p in before}
    assert {"case_stage", "case_value", "medical_bill", "party"} <= kinds

    _fake_model(monkeypatch, _failures)
    mapping = build_mapping(matter, MATTER)

    assert _code_facts(matter) == before
    assert mapping.providers() == {PROVIDER: "Invented Clinic"}
    assert len(mapping.errors) == 3


def test_a_digest_whose_mapping_failed_does_not_report_itself_clean(
    data_dir: Path, matter: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_model(monkeypatch, _answers)
    build_mapping(matter, MATTER)

    _fake_model(monkeypatch, _failures)
    run = run_digest(matter, MATTER)

    assert run.error is not None and "mapping" in run.error.lower()
