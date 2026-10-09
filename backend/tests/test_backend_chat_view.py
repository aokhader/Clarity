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
from app.services.incident import incident_fact
from app.services.jobs import cached_failed_calls
from app.services.matter_queries import matter_stage
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


def test_a_sentences_chips_are_the_facts_it_cites_in_the_models_order(
    seeded: Session,
) -> None:
    injury = _fact(seeded, FactKind.INJURY)  # A: states no amount
    offer = _fact(seeded, FactKind.OFFER)  # B: the only fact stating $40,000
    thread = _done_turn(
        seeded,
        [
            ("The client has a neck strain; the offer is $40,000.", [injury.id], False),
            # Also today's bills total, which no cited fact states.
            ("The medical bills come to $3,440.", [injury.id], False),
            (
                "The insurer offered $40,000 for the neck strain.",
                [offer.id, injury.id],
                False,
            ),
        ],
    )

    [turn] = chat_view.thread_out(seeded, thread).turns

    amount_only_b_states, total, both = turn.sentences
    # A figure other records state keeps its verdict, and its mention names them, but
    # adds no chip: a record sharing only an amount may not hold the sentence (D51).
    assert amount_only_b_states.verdict == "supported"
    assert [r.id for r in amount_only_b_states.facts] == [injury.id]
    [mention] = amount_only_b_states.mentions
    assert mention.verdict == "supported" and offer.id in {r.id for r in mention.facts}
    assert total.verdict == "supported"
    assert [r.id for r in total.facts] == [injury.id]
    # The model's order holds, not the fact ids' or the file's.
    assert [r.id for r in both.facts] == [offer.id, injury.id]


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


def test_the_overview_is_capped_with_the_stage_and_incident_first(
    seeded: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    renderable = load_renderable(seeded, MATTER_ID)
    by_kind = [f for f in renderable.values() if f.kind is FactKind.INCIDENT]
    incident = incident_fact(by_kind)
    assert incident is not None
    first = [r.id for r in matter_stage(seeded, MATTER_ID).facts] + [incident.id]

    def overview() -> list[int]:
        context = chat_context.build_context(
            seeded, MATTER_ID, "What is next?", [], [], renderable=renderable
        )
        return [f.id for f in context.overview]

    shown = overview()
    assert len(shown) <= chat_context.OVERVIEW_FACT_CAP
    assert shown[: len(first)] == first
    # Under a cap that leaves room for nothing else, the stage and incident still lead
    # and the brief's sentences keep every id they cite.
    monkeypatch.setattr(chat_context, "OVERVIEW_FACT_CAP", len(first))
    assert overview() == first
    context = chat_context.build_context(
        seeded, MATTER_ID, "What is next?", [], [], renderable=renderable
    )
    assert context.brief_sentences and all(ids for _, ids in context.brief_sentences)


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
