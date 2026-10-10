"""What a pointed-at stage resolves to (D51): the stage, then what moved the case."""

from collections.abc import Iterator
from datetime import date, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import Fact, FactKind
from app.schemas import AskStageRef
from app.services.chat_attachments import resolve_items
from app.services.matter_queries import matter_stage
from tests.fixtures.synthetic_matter import MATTER_ID


@pytest.fixture(autouse=True)
def no_operator_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _only(session: Session, kind: FactKind) -> Fact:
    [fact] = session.scalars(
        select(Fact).where(Fact.matter_id == MATTER_ID, Fact.kind == kind)
    ).all()
    return fact


def _like(session: Session, fact: Fact, on: date | None) -> Fact:
    """Another fact of `fact`'s kind from its record, dated `on`."""
    other = Fact(
        matter_id=MATTER_ID,
        kind=fact.kind,
        title=f"Another {fact.kind.value}",
        value_json=fact.value_json,
        event_date=on,
        source_id=fact.source_id,
        quote=fact.quote,
        significance=fact.significance,
        confidence=fact.confidence,
        origin=fact.origin,
    )
    session.add(other)
    session.commit()
    return other


def test_a_stage_item_is_the_stage_then_the_dated_moves_latest_first(
    seeded: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    stage = _only(seeded, FactKind.CASE_STAGE)
    assert [r.id for r in matter_stage(seeded, MATTER_ID).facts] == [stage.id]
    earlier = _only(seeded, FactKind.STATUS_CHANGE)
    filed = _only(seeded, FactKind.LITIGATION_EVENT)
    assert earlier.event_date and filed.event_date
    assert earlier.event_date < filed.event_date
    later = _like(seeded, earlier, filed.event_date + timedelta(days=30))
    _like(seeded, filed, None)  # an undated court event moved nothing on a day

    def resolved() -> tuple[str, list[int]]:
        [item] = resolve_items(seeded, MATTER_ID, [AskStageRef(kind="stage")])
        return item.label, [f.id for f in item.facts]

    assert resolved() == ("Case stage", [stage.id, later.id, filed.id, earlier.id])
    # The cap counts the stage facts, which come first.
    monkeypatch.setenv("CHAT_ITEM_FACTS", "2")
    get_settings.cache_clear()
    assert resolved() == ("Case stage", [stage.id, later.id])
