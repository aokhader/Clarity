"""A closed thread's chips open the sources frozen when it closed (D54), on the synthetic
matter. A re-read is simulated by deleting or replacing the cited fact and changing its
page's text; the frozen route must still serve what was cited. No model is called.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.digest import llm
from app.models import (
    ChatFrozenSource,
    ChatStatus,
    ChatThread,
    ChatTurn,
    Confidence,
    Fact,
    FactKind,
    Origin,
    Page,
    Source,
    SourceType,
    User,
)
from app.schemas import DraftMentionOut
from app.services import chat_view
from app.services.chat_frozen import GONE
from app.services.fact_views import fact_ref
from tests.fixtures.synthetic_matter import MATTER_ID, ORTHO_ID

OTHER_MATTER = MATTER_ID + 1
CHAT = f"/api/matters/{MATTER_ID}/chat"


@pytest.fixture(autouse=True)
def no_model_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings come from the test alone, and a model call fails the test."""
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()

    def refuse(request: object) -> None:
        raise AssertionError("a model call was attempted")

    monkeypatch.setattr(llm, "_execute", refuse)


@pytest.fixture
def user_id(seeded: Session) -> int:
    return seeded.scalars(select(User.id).order_by(User.id)).first() or 0


def _fact(session: Session, kind: FactKind, provider: int | None = None) -> Fact:
    query = select(Fact).where(Fact.matter_id == MATTER_ID, Fact.kind == kind)
    if provider is not None:
        query = query.where(Fact.provider_contact_id == provider)
    fact = session.scalars(query.order_by(Fact.id)).first()
    assert fact is not None
    return fact


def _answered_thread(
    session: Session, user_id: int, sentence_ids: list[int], item_ids: list[int]
) -> int:
    """A thread with one answered turn: one sentence citing `sentence_ids`, and one
    item pointing at `item_ids`."""
    thread = ChatThread(matter_id=MATTER_ID, created_by=user_id, title="Billed?")
    session.add(thread)
    session.flush()
    session.add(
        ChatTurn(
            thread_id=thread.id,
            matter_id=MATTER_ID,
            asked_by=user_id,
            question="What has the provider billed?",
            items_json=[{"kind": "facts", "fact_ids": item_ids}] if item_ids else [],
            status=ChatStatus.DONE,
            answer_json={
                "sentences": [
                    {
                        "text": "The orthopedic office billed $2,480.",
                        "fact_ids": sentence_ids,
                        "not_in_file": False,
                    }
                ],
                "no_answer": False,
                "dropped": 0,
            },
        )
    )
    session.commit()
    return thread.id


def _close(client: TestClient, user_id: int, thread_id: int) -> dict[str, Any]:
    response = client.post(
        f"{CHAT}/threads/{thread_id}/close", headers={"X-User-Id": str(user_id)}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _frozen(
    client: TestClient, thread_id: int, fact_id: int, matter_id: int = MATTER_ID
) -> Any:
    return client.get(
        f"/api/matters/{matter_id}/chat/threads/{thread_id}/facts/{fact_id}/source"
    )


def _cut_to_page(served: dict[str, Any]) -> dict[str, Any]:
    """The drawer's answer with its source's pages cut to the fact's page (D54)."""
    page_no = served["fact"]["page_no"]
    if page_no is None:
        return served
    pages = [p for p in served["source"]["pages"] if p["page_no"] == page_no]
    return served | {"source": served["source"] | {"pages": pages}}


def _simulate_re_read(session: Session, fact: Fact) -> None:
    """A re-read deletes the fact and rewrites its page's text."""
    page = session.scalars(
        select(Page).where(
            Page.source_id == fact.source_id, Page.page_no == fact.page_no
        )
    ).one()
    page.text = "Re-read text"
    session.delete(fact)
    session.commit()


def _frozen_rows(session: Session, thread_id: int) -> int:
    session.expire_all()
    return (
        session.scalar(
            select(func.count())
            .select_from(ChatFrozenSource)
            .where(ChatFrozenSource.thread_id == thread_id)
        )
        or 0
    )


@pytest.fixture
def other_matter(seeded: Session) -> None:
    seeded.add(
        Source(
            matter_id=OTHER_MATTER,
            clio_type=SourceType.MATTER,
            clio_id=str(OTHER_MATTER),
            raw_json={"id": OTHER_MATTER},
        )
    )
    seeded.commit()


# --- Closing freezes ---------------------------------------------------------------------


def test_closing_freezes_each_cited_source_as_the_drawer_served_it_cut_to_its_page(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    bill = _fact(seeded, FactKind.MEDICAL_BILL, ORTHO_ID)
    injury = _fact(seeded, FactKind.INJURY, ORTHO_ID)
    undated_page = seeded.scalars(
        select(Fact).where(Fact.matter_id == MATTER_ID, Fact.page_no.is_(None))
    ).first()
    assert undated_page is not None
    # One fact cited twice: by the sentence and by the item.
    thread_id = _answered_thread(
        seeded, user_id, [bill.id, injury.id], [bill.id, undated_page.id]
    )
    live = {
        f.id: client.get(f"/api/facts/{f.id}/source").json()
        for f in (bill, injury, undated_page)
    }
    assert len(live[bill.id]["source"]["pages"]) == 2  # the document has two pages

    _close(client, user_id, thread_id)

    assert _frozen_rows(seeded, thread_id) == 3
    for fact_id, served in live.items():
        response = _frozen(client, thread_id, fact_id)
        assert response.status_code == 200, response.text
        assert response.json() == _cut_to_page(served)
    [bill_page] = _frozen(client, thread_id, bill.id).json()["source"]["pages"]
    [injury_page] = _frozen(client, thread_id, injury.id).json()["source"]["pages"]
    assert (bill_page["page_no"], injury_page["page_no"]) == (2, 1)
    assert bill_page["text"] is None  # the second page is a scan
    assert injury_page["text"]


def test_a_re_read_leaves_the_frozen_source_as_cited_while_the_live_drawer_404s(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    injury = _fact(seeded, FactKind.INJURY, ORTHO_ID)
    injury_id, quote = injury.id, injury.quote
    thread_id = _answered_thread(seeded, user_id, [injury_id], [])
    before = _cut_to_page(client.get(f"/api/facts/{injury_id}/source").json())
    [page_before] = before["source"]["pages"]
    assert page_before["text"]  # the cited page has a text layer
    _close(client, user_id, thread_id)

    _simulate_re_read(seeded, injury)

    assert client.get(f"/api/facts/{injury_id}/source").status_code == 404
    response = _frozen(client, thread_id, injury_id)
    assert response.status_code == 200, response.text
    frozen = response.json()
    assert frozen == before
    assert frozen["fact"]["quote"] == quote
    [page] = frozen["source"]["pages"]
    assert page["text"] == page_before["text"]


def test_an_id_a_re_read_gives_another_fact_still_opens_the_cited_source(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    bill = _fact(seeded, FactKind.MEDICAL_BILL, ORTHO_ID)
    bill_id, source_id = bill.id, bill.source_id
    thread_id = _answered_thread(seeded, user_id, [bill_id], [])
    before = _cut_to_page(client.get(f"/api/facts/{bill_id}/source").json())
    _close(client, user_id, thread_id)
    seeded.delete(bill)
    seeded.flush()
    seeded.add(
        Fact(
            id=bill_id,
            matter_id=MATTER_ID,
            kind=FactKind.OTHER,
            title="A different finding",
            value_json={},
            source_id=source_id,
            page_no=1,
            quote="A different quote",
            confidence=Confidence.HIGH,
            origin=Origin.MODEL,
        )
    )
    seeded.commit()

    assert client.get(f"/api/facts/{bill_id}/source").json()["fact"]["title"] == (
        "A different finding"
    )
    assert _frozen(client, thread_id, bill_id).json() == before


def test_a_figure_marks_chip_is_frozen_with_the_sentences_chips(
    seeded: Session,
    client: TestClient,
    user_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A "differs" mark cites the fact holding the file's figure, which need not be one
    of the sentence's chips; the closed thread's mark must still open it."""
    bill = _fact(seeded, FactKind.MEDICAL_BILL, ORTHO_ID)
    lien = _fact(seeded, FactKind.LIEN)
    bill_id, lien_id = bill.id, lien.id
    mark = DraftMentionOut(
        start=29,
        end=35,
        text="$2,480",
        kind="amount",
        verdict="differs",
        reason="the file states another figure",
        facts=[fact_ref(lien)],
        file_amount_cents=248_000,
        file_date=None,
    )
    monkeypatch.setattr(
        chat_view, "check_sentence", lambda text, cited, file: ("differs", [mark])
    )
    thread_id = _answered_thread(seeded, user_id, [bill_id], [])
    before = _cut_to_page(client.get(f"/api/facts/{lien_id}/source").json())

    [turn] = _close(client, user_id, thread_id)["turns"]

    [sentence] = turn["sentences"]
    assert [f["id"] for f in sentence["facts"]] == [bill_id]
    assert [f["id"] for f in sentence["mentions"][0]["facts"]] == [lien_id]
    assert _frozen_rows(seeded, thread_id) == 2
    assert _frozen(client, thread_id, lien_id).json() == before
    # A thread closed before D54 freezes the mark's fact on first open, too.
    seeded.execute(delete(ChatFrozenSource))
    seeded.commit()
    backfilled = _frozen(client, thread_id, lien_id)
    assert backfilled.status_code == 200, backfilled.text
    assert backfilled.json() == before
    _simulate_re_read(seeded, seeded.get(Fact, lien_id))
    assert _frozen(client, thread_id, lien_id).json() == before


# --- Who may open it ------------------------------------------------------------------------


def test_the_frozen_route_is_404_for_an_open_thread_an_uncited_fact_or_another_matter(
    seeded: Session, client: TestClient, user_id: int, other_matter: None
) -> None:
    bill = _fact(seeded, FactKind.MEDICAL_BILL, ORTHO_ID)
    lien = _fact(seeded, FactKind.LIEN)
    thread_id = _answered_thread(seeded, user_id, [bill.id], [])

    assert _frozen(client, thread_id, bill.id).status_code == 404  # still open
    _close(client, user_id, thread_id)
    assert _frozen(client, thread_id, bill.id).status_code == 200
    assert _frozen(client, thread_id, lien.id).status_code == 404  # not cited
    assert _frozen(client, thread_id, bill.id, OTHER_MATTER).status_code == 404
    assert _frozen(client, thread_id + 1, bill.id).status_code == 404  # no thread


# --- Threads closed before D54 --------------------------------------------------------------


def test_a_thread_closed_before_d54_freezes_a_source_the_first_time_it_is_opened(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    bill = _fact(seeded, FactKind.MEDICAL_BILL, ORTHO_ID)
    lien = _fact(seeded, FactKind.LIEN)
    bill_id, lien_id = bill.id, lien.id
    thread_id = _answered_thread(seeded, user_id, [bill_id, lien_id], [])
    before = _cut_to_page(client.get(f"/api/facts/{bill_id}/source").json())
    _close(client, user_id, thread_id)
    seeded.execute(delete(ChatFrozenSource))  # as a thread closed before D54 has
    seeded.commit()

    first = _frozen(client, thread_id, bill_id)

    assert first.status_code == 200, first.text
    assert first.json() == before
    assert _frozen_rows(seeded, thread_id) == 1  # only what was opened
    # Once frozen, a re-read no longer reaches it.
    _simulate_re_read(seeded, seeded.get(Fact, bill_id))
    assert _frozen(client, thread_id, bill_id).json() == before
    # A fact a re-read removed before its first open cannot be frozen any more.
    seeded.delete(seeded.get(Fact, lien_id))
    seeded.commit()
    gone = _frozen(client, thread_id, lien_id)
    assert gone.status_code == 404
    assert gone.json()["detail"] == GONE


def test_the_backfill_refuses_an_id_that_now_names_a_fact_on_another_page(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    bill = _fact(seeded, FactKind.MEDICAL_BILL, ORTHO_ID)
    bill_id = bill.id
    thread_id = _answered_thread(seeded, user_id, [bill_id], [])
    _close(client, user_id, thread_id)
    seeded.execute(delete(ChatFrozenSource))
    bill = seeded.get(Fact, bill_id)
    assert bill is not None and bill.page_no == 2
    bill.page_no = 1  # a re-read gave the id to a finding on another page
    seeded.commit()

    response = _frozen(client, thread_id, bill_id)

    assert response.status_code == 404
    assert response.json()["detail"] == GONE
    assert _frozen_rows(seeded, thread_id) == 0
