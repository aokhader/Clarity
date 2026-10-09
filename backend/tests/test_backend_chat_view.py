"""A chat turn served against today's file (D49, D12), and chat kept out of the digest's
figures. The turns are written straight to the database; no model is involved."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import ChatStatus, ChatThread, ChatTurn, Fact, FactKind, LlmCall
from app.services import chat_context, chat_view
from app.services.chat_attachments import load_renderable
from app.services.jobs import cached_failed_calls
from tests.fixtures.synthetic_matter import MATTER_ID, ORTHO_ID


@pytest.fixture(autouse=True)
def no_operator_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _fact(session: Session, kind: FactKind, provider: int | None = None) -> Fact:
    query = select(Fact).where(Fact.matter_id == MATTER_ID, Fact.kind == kind)
    if provider is not None:
        query = query.where(Fact.provider_contact_id == provider)
    fact = session.scalars(query.order_by(Fact.id)).first()
    assert fact is not None
    return fact


def _done_turn(
    session: Session,
    sentences: list[tuple[str, list[int], bool]],
    items: list[dict[str, object]] | None = None,
) -> ChatThread:
    now = datetime.now(UTC)
    thread = ChatThread(matter_id=MATTER_ID, title="A question", created_at=now)
    session.add(thread)
    session.add(
        ChatTurn(
            thread=thread,
            matter_id=MATTER_ID,
            question="A question",
            items_json=items or [],
            status=ChatStatus.DONE,
            answer_json={
                "sentences": [
                    {"text": text, "fact_ids": ids, "not_in_file": not_in_file}
                    for text, ids, not_in_file in sentences
                ],
                "no_answer": False,
                "dropped": 0,
            },
            created_at=now,
            finished_at=now,
        )
    )
    session.commit()
    return thread


def test_a_sentence_citing_a_fact_that_can_no_longer_be_shown_is_withdrawn(
    seeded: Session,
) -> None:
    injury = _fact(seeded, FactKind.INJURY)  # read from a document page
    bill = _fact(seeded, FactKind.MEDICAL_BILL, ORTHO_ID)
    thread = _done_turn(
        seeded,
        [
            ("The client has a neck strain.", [injury.id], False),
            ("The orthopedic office billed $2,480.", [bill.id], False),
        ],
        items=[{"kind": "facts", "fact_ids": [injury.id]}],
    )
    # A document fact without its quote cannot be rendered (rule 3).
    injury.quote = None
    seeded.commit()

    [turn] = chat_view.thread_out(seeded, thread).turns

    assert [s.text for s in turn.sentences] == ["The orthopedic office billed $2,480."]
    assert turn.withdrawn == 1
    # The item no longer resolves: it keeps a generic label and no facts.
    [item] = turn.items
    assert item.label == "Records" and item.facts == []


def test_an_amount_that_differs_from_the_file_is_marked_with_the_files_figure(
    seeded: Session,
) -> None:
    bills = seeded.scalars(
        select(Fact).where(
            Fact.matter_id == MATTER_ID, Fact.kind == FactKind.MEDICAL_BILL
        )
    ).all()
    thread = _done_turn(
        seeded, [("The medical bills total $9,999.", [b.id for b in bills], False)]
    )

    [turn] = chat_view.thread_out(seeded, thread).turns

    [sentence] = turn.sentences
    assert sentence.verdict == "differs"
    [mention] = sentence.mentions
    assert mention.text == "$9,999" and mention.verdict == "differs"
    # Today's bills total, each charge counted once: $2,480 and $960.
    assert mention.file_amount_cents == 344_000


def test_a_not_in_file_sentence_cites_nothing_and_is_unchecked(seeded: Session) -> None:
    thread = _done_turn(seeded, [("The file does not say.", [], True)])

    [turn] = chat_view.thread_out(seeded, thread).turns

    [sentence] = turn.sentences
    assert sentence.not_in_file and sentence.facts == []
    assert sentence.verdict == "unchecked" and sentence.mentions == []


def test_the_ranker_puts_a_word_at_a_title_start_and_the_named_kind_first(
    seeded: Session,
) -> None:
    facts = list(load_renderable(seeded, MATTER_ID).values())

    ranked = chat_context.rank_facts(facts, "What are the liens?")

    assert ranked[0].kind is FactKind.LIEN
    assert len(ranked) == len(facts)  # retrieval keeps every fact, best first
    matching = chat_context.rank_facts(facts, "lien", matching_only=True)
    assert {f.kind for f in matching} == {FactKind.LIEN}


def test_cached_failed_calls_leave_chat_out(seeded: Session) -> None:
    def failed(purpose: str, key: str) -> LlmCall:
        return LlmCall(
            matter_id=MATTER_ID,
            purpose=purpose,
            model="m",
            cache_key=key,
            response_json=None,
            error="HTTP 529",
        )

    seeded.add(failed("chat", "chat-key"))
    seeded.commit()
    assert cached_failed_calls(seeded) == 0

    seeded.add(failed("extract_page", "page-key"))
    seeded.commit()
    assert cached_failed_calls(seeded) == 1
