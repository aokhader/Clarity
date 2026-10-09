"""The chatbot's routes (D49, docs/chat-contract.md) on the synthetic matter.

Pipeline's `answer_question` calls a model, so these tests swap in an invented one,
and every test refuses a real model call outright. Nothing here reaches a provider.
"""

import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.digest import llm
from app.digest.chat import ChatAnswer, ChatAnswerSentence, ChatInput
from app.main import app
from app.models import (
    Call,
    ChatStatus,
    ChatThread,
    ChatTurn,
    Confidence,
    Fact,
    FactKind,
    LlmCall,
    Origin,
    Source,
    SourceType,
    User,
)
from app.services import chat
from app.services.source_views import source_name
from tests.fixtures.synthetic_matter import MATTER_ID, ORTHO_ID

OTHER_MATTER = MATTER_ID + 1
POLL_S = 10.0
ANSWER_COST = 1234


@pytest.fixture(autouse=True)
def no_model_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings come from the test alone, never the operator's .env, and a real model
    call fails the test."""
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()

    def refuse(request: object) -> None:
        raise AssertionError("a model call was attempted")

    monkeypatch.setattr(llm, "_execute", refuse)


@pytest.fixture
def chat_on(data_dir: object, monkeypatch: pytest.MonkeyPatch) -> None:
    """Chat settings as an operator would set them; the key is never used."""
    monkeypatch.setenv("LLM_API_KEY", "test-key-not-real")
    monkeypatch.setenv("CHAT_MODEL", "test-chat-model")
    monkeypatch.setenv("CHAT_PRICE_IN", "2")
    monkeypatch.setenv("CHAT_PRICE_OUT", "10")
    monkeypatch.setenv("CHAT_DAILY_BUDGET_USD", "2")
    get_settings.cache_clear()


@pytest.fixture
def chat_off(data_dir: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CHAT_MODEL", raising=False)
    get_settings.cache_clear()


@pytest.fixture
def user_id(seeded: Session) -> int:
    return seeded.scalars(select(User.id).order_by(User.id)).first() or 0


@pytest.fixture
def no_start(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Leave turns running: record the starts instead of answering."""
    started: list[int] = []
    monkeypatch.setattr(chat, "start", started.append)
    return started


Answer = Callable[[Session, ChatInput], ChatAnswer]


def _use_answerer(
    monkeypatch: pytest.MonkeyPatch, answer: Answer | Exception
) -> list[ChatInput]:
    seen: list[ChatInput] = []

    def answer_question(
        session: Session, *, matter_id: int, question: str, chat_input: ChatInput
    ) -> ChatAnswer:
        assert matter_id == MATTER_ID and question
        seen.append(chat_input)
        if isinstance(answer, Exception):
            raise answer
        return answer(session, chat_input)

    monkeypatch.setattr(chat, "_answerer", lambda: answer_question)
    return seen


def _paid_call(
    session: Session, cost: int = ANSWER_COST, at: datetime | None = None
) -> int:
    row = LlmCall(
        matter_id=MATTER_ID,
        purpose="chat",
        model="test-chat-model",
        cache_key="chat-test",
        response_json={},
        cost_micro_usd=cost,
        created_at=at or datetime.now(UTC),
    )
    session.add(row)
    session.flush()
    return row.id


def _citing(*sentences: tuple[str, list[int]]) -> Answer:
    def answer(session: Session, chat_input: ChatInput) -> ChatAnswer:
        return ChatAnswer(
            sentences=[
                ChatAnswerSentence(text=text, fact_ids=ids, not_in_file=not ids)
                for text, ids in sentences
            ],
            no_answer=False,
            dropped=0,
            llm_call_id=_paid_call(session),
            error=None,
        )

    return answer


def _fact(session: Session, kind: FactKind, provider: int | None = None) -> Fact:
    query = select(Fact).where(Fact.matter_id == MATTER_ID, Fact.kind == kind)
    if provider is not None:
        query = query.where(Fact.provider_contact_id == provider)
    fact = session.scalars(query.order_by(Fact.id)).first()
    assert fact is not None
    return fact


def _ask(
    client: TestClient, user_id: int, matter_id: int = MATTER_ID, **body: Any
) -> Any:
    return client.post(
        f"/api/matters/{matter_id}/chat/ask",
        json={"question": "What has the provider billed?", "items": []} | body,
        headers={"X-User-Id": str(user_id)},
    )


def _settled(client: TestClient, thread_id: int) -> dict[str, Any]:
    deadline = time.monotonic() + POLL_S
    while time.monotonic() < deadline:
        thread = client.get(f"/api/matters/{MATTER_ID}/chat/threads/{thread_id}")
        assert thread.status_code == 200, thread.text
        if all(t["status"] != "running" for t in thread.json()["turns"]):
            return thread.json()
        time.sleep(0.05)
    raise AssertionError("the answer was still running")


def _count(session: Session, model: type) -> int:
    session.expire_all()
    return session.scalar(select(func.count()).select_from(model)) or 0


@pytest.fixture
def other_matter(seeded: Session) -> Iterator[dict[str, int]]:
    """A second, minimal matter: one note and one fact on it."""
    matter = Source(
        matter_id=OTHER_MATTER,
        clio_type=SourceType.MATTER,
        clio_id=str(OTHER_MATTER),
        raw_json={"id": OTHER_MATTER},
    )
    note = Source(
        matter_id=OTHER_MATTER,
        clio_type=SourceType.NOTE,
        clio_id="9001",
        raw_json={"id": 9001, "subject": "Other", "detail": "Another matter"},
    )
    seeded.add_all([matter, note])
    seeded.flush()
    fact = Fact(
        matter_id=OTHER_MATTER,
        kind=FactKind.OTHER,
        title="A fact of another matter",
        value_json={},
        source_id=note.id,
        confidence=Confidence.HIGH,
        origin=Origin.MODEL,
    )
    call = Call(
        matter_id=OTHER_MATTER, target_json={}, consent_text="Agreed", transcript=""
    )
    seeded.add_all([fact, call])
    seeded.commit()
    yield {"fact": fact.id, "source": note.id, "call": call.id}


# --- Asking and answering ---------------------------------------------------------------


def test_a_question_is_answered_in_the_background_with_cited_sentences(
    chat_on: None,
    seeded: Session,
    client: TestClient,
    user_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bill = _fact(seeded, FactKind.MEDICAL_BILL, ORTHO_ID)
    seen = _use_answerer(
        monkeypatch,
        _citing(
            ("The orthopedic office billed $2,480.", [bill.id]),
            ("The file does not say whether the bill was paid.", []),
        ),
    )

    asked = _ask(client, user_id, items=[{"kind": "facts", "fact_ids": [bill.id]}])

    assert asked.status_code == 202, asked.text
    turn = asked.json()
    assert turn["status"] in ("running", "done")
    [item] = turn["items"]
    assert item["label"].startswith("Bill, ")
    assert bill.id in [f["id"] for f in item["facts"]]

    thread = _settled(client, turn["thread_id"])
    [done] = thread["turns"]
    assert done["status"] == "done" and done["error"] is None
    cited, uncited = done["sentences"]
    assert [f["id"] for f in cited["facts"]] == [bill.id]
    assert cited["verdict"] == "supported" and not cited["not_in_file"]
    assert uncited["not_in_file"] and uncited["facts"] == []
    assert uncited["verdict"] == "unchecked"
    assert done["cost_micro_usd"] == ANSWER_COST
    assert done["answered_at"] is not None and done["withdrawn"] == 0
    assert done["asked_by"] == seeded.get(User, user_id).name
    assert thread["title"] == "What has the provider billed?"

    # The pointed-at bill comes first, and is not repeated among the retrieved facts.
    [chat_input] = seen
    assert bill.id in [f.id for f in chat_input.attached[0].facts]
    assert bill.id not in [f.id for f in chat_input.retrieved]
    assert chat_input.overview and chat_input.brief_sentences
    stored = seeded.get(ChatTurn, done["turn_id"])
    assert stored is not None and bill.id in (stored.context_fact_ids_json or [])

    listed = client.get(f"/api/matters/{MATTER_ID}/chat/threads").json()
    assert [(t["thread_id"], t["turn_count"], t["last_status"]) for t in listed] == [
        (turn["thread_id"], 1, "done")
    ]


def test_a_follow_up_carries_the_earlier_turn(
    chat_on: None,
    seeded: Session,
    client: TestClient,
    user_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bill = _fact(seeded, FactKind.MEDICAL_BILL, ORTHO_ID)
    seen = _use_answerer(
        monkeypatch, _citing(("The orthopedic office billed $2,480.", [bill.id]))
    )
    first = _ask(client, user_id).json()
    _settled(client, first["thread_id"])

    second = _ask(
        client, user_id, question="And the lien?", thread_id=first["thread_id"]
    )

    assert second.status_code == 202, second.text
    thread = _settled(client, first["thread_id"])
    assert len(thread["turns"]) == 2
    [prior] = seen[1].history
    assert prior.question == "What has the provider billed?"
    assert prior.answer == "The orthopedic office billed $2,480."


def test_each_item_kind_resolves_inside_the_matter(
    chat_on: None,
    seeded: Session,
    client: TestClient,
    user_id: int,
    no_start: list[int],
) -> None:
    document = _fact(seeded, FactKind.MEDICAL_BILL, ORTHO_ID).source_id
    call_source = seeded.scalars(
        select(Source.id).where(
            Source.matter_id == MATTER_ID, Source.clio_type == SourceType.CALL
        )
    ).first()
    call = Call(
        matter_id=MATTER_ID,
        target_json={},
        consent_text="Agreed",
        source_id=call_source,
    )
    seeded.add(call)
    seeded.commit()

    asked = _ask(
        client,
        user_id,
        items=[
            {"kind": "source", "source_id": document},
            {"kind": "provider", "contact_id": ORTHO_ID},
            {"kind": "call", "call_id": call.id},
            {"kind": "kpi", "name": "medical_specials"},
            {"kind": "stage"},
        ],
    )

    assert asked.status_code == 202, asked.text
    labels = [i["label"] for i in asked.json()["items"]]
    assert labels[0].startswith("Document")
    assert labels[1].startswith("Provider")
    assert labels[2].startswith("Call, ")
    assert labels[3:] == ["Medical specials", "Case stage"]
    assert all(i["facts"] for i in asked.json()["items"])
    assert no_start  # chat is on, so the answer was started


def test_a_blank_question_is_refused(
    chat_on: None, seeded: Session, client: TestClient, user_id: int
) -> None:
    assert _ask(client, user_id, question="   ").status_code == 422
    assert _count(seeded, ChatTurn) == 0


# --- The matter boundary ----------------------------------------------------------------


def test_an_item_from_another_matter_is_refused_and_nothing_is_stored(
    chat_on: None,
    seeded: Session,
    client: TestClient,
    user_id: int,
    other_matter: dict[str, int],
    no_start: list[int],
) -> None:
    refused = [
        {"kind": "facts", "fact_ids": [other_matter["fact"]]},
        {"kind": "source", "source_id": other_matter["source"]},
        {"kind": "call", "call_id": other_matter["call"]},
        {"kind": "provider", "contact_id": 987654},
    ]
    for item in refused:
        response = _ask(client, user_id, items=[item])
        assert response.status_code == 422, item

    assert _count(seeded, ChatTurn) == 0 and _count(seeded, ChatThread) == 0
    assert no_start == []


def test_a_thread_or_turn_is_found_only_under_its_own_matter(
    chat_on: None,
    seeded: Session,
    client: TestClient,
    user_id: int,
    other_matter: dict[str, int],
    no_start: list[int],
) -> None:
    turn = _ask(client, user_id).json()
    thread_id = turn["thread_id"]
    other = f"/api/matters/{OTHER_MATTER}/chat"
    header = {"X-User-Id": str(user_id)}

    assert client.get(f"{other}/threads/{thread_id}").status_code == 404
    assert client.get(f"{other}/threads").json() == []
    assert _ask(client, user_id, OTHER_MATTER, thread_id=thread_id).status_code == 404
    retried = client.post(f"{other}/turns/{turn['turn_id']}/retry", headers=header)
    assert retried.status_code == 404
    closed = client.post(f"{other}/threads/{thread_id}/close", headers=header)
    assert closed.status_code == 404
    assert client.get("/api/matters/424242/chat/threads").status_code == 404


def test_no_chat_or_search_route_sits_under_the_provider_prefix() -> None:
    # Every mounted route, as the schema lists it; no route here is left out of it.
    paths = list(app.openapi()["paths"])
    provider = [p for p in paths if p.startswith("/api/p/") or p == "/api/p"]
    assert provider, "the provider routes are mounted"
    assert not [p for p in provider if "chat" in p or "search" in p]
    chat_paths = [p for p in paths if "/chat" in p or p.endswith("/search")]
    assert len(chat_paths) == 9  # D54 added the frozen source
    assert all(p.startswith("/api/matters/{matter_id}/") for p in chat_paths)


# --- No model call on a read --------------------------------------------------------------


def test_reading_chat_never_calls_a_model(
    chat_on: None,
    seeded: Session,
    client: TestClient,
    user_id: int,
    no_start: list[int],
) -> None:
    calls_before = _count(seeded, LlmCall)

    asked = _ask(client, user_id)

    assert asked.status_code == 202 and asked.json()["status"] == "running"
    thread_id = asked.json()["thread_id"]
    base = f"/api/matters/{MATTER_ID}"
    for path in (
        f"{base}/chat/threads",
        f"{base}/chat/threads/{thread_id}",
        f"{base}/chat/budget",
        f"{base}/search?q=bill",
    ):
        assert client.get(path).status_code == 200, path
    # The POST stored the turn and handed it to the background run, nothing more.
    assert _count(seeded, LlmCall) == calls_before
    assert no_start == [asked.json()["turn_id"]]


# --- Settings, spend and recovery --------------------------------------------------------


def test_unconfigured_chat_stores_a_no_model_turn(
    chat_off: None,
    seeded: Session,
    client: TestClient,
    user_id: int,
    no_start: list[int],
) -> None:
    asked = _ask(client, user_id)

    assert asked.status_code == 202
    assert asked.json()["status"] == "no_model"
    assert no_start == []
    assert (
        client.get(f"/api/matters/{MATTER_ID}/chat/budget").json()["configured"]
        is False
    )


def test_over_the_daily_cap_ask_and_retry_are_refused(
    chat_on: None,
    seeded: Session,
    client: TestClient,
    user_id: int,
    monkeypatch: pytest.MonkeyPatch,
    no_start: list[int],
) -> None:
    monkeypatch.setenv("CHAT_DAILY_BUDGET_USD", "0.01")  # 10,000 micro-dollars
    get_settings.cache_clear()
    turn = _ask(client, user_id).json()
    failed = seeded.get(ChatTurn, turn["turn_id"])
    assert failed is not None
    failed.status = ChatStatus.FAILED
    # Yesterday's spend and the digest's do not count against today's chat cap.
    _paid_call(seeded, cost=50_000, at=datetime.now(UTC) - timedelta(days=2))
    seeded.add(
        LlmCall(
            matter_id=MATTER_ID,
            purpose="extract_page",
            model="m",
            cache_key="digest",
            cost_micro_usd=50_000,
        )
    )
    seeded.commit()
    assert _ask(client, user_id, question="Still under the cap?").status_code == 202

    _paid_call(seeded, cost=10_000)
    seeded.commit()
    turns_before = _count(seeded, ChatTurn)

    assert _ask(client, user_id, question="Over the cap?").status_code == 429
    retried = client.post(
        f"/api/matters/{MATTER_ID}/chat/turns/{turn['turn_id']}/retry",
        headers={"X-User-Id": str(user_id)},
    )
    assert retried.status_code == 429
    assert _count(seeded, ChatTurn) == turns_before
    budget = client.get(f"/api/matters/{MATTER_ID}/chat/budget").json()
    assert budget["spent_today_micro_usd"] == 10_000
    assert budget["cap_micro_usd"] == 10_000
    assert datetime.fromisoformat(budget["resets_at"]) > datetime.now(UTC)


def test_the_startup_sweep_fails_turns_left_running(
    chat_on: None,
    seeded: Session,
    client: TestClient,
    user_id: int,
    no_start: list[int],
) -> None:
    turn = _ask(client, user_id).json()
    assert turn["status"] == "running"

    with TestClient(app):  # a restart: the lifespan runs again
        pass

    thread = client.get(f"/api/matters/{MATTER_ID}/chat/threads/{turn['thread_id']}")
    [swept] = thread.json()["turns"]
    assert swept["status"] == "failed" and swept["error"] == "Interrupted; ask again"


def test_a_running_turn_blocks_another_question_in_its_thread(
    chat_on: None,
    seeded: Session,
    client: TestClient,
    user_id: int,
    no_start: list[int],
) -> None:
    turn = _ask(client, user_id).json()

    again = _ask(
        client, user_id, question="Anything else?", thread_id=turn["thread_id"]
    )

    assert again.status_code == 409


def test_retry_asks_again_only_a_failed_or_unanswered_turn(
    chat_off: None,
    seeded: Session,
    client: TestClient,
    user_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unanswered = _ask(client, user_id).json()
    assert unanswered["status"] == "no_model"
    retry_path = f"/api/matters/{MATTER_ID}/chat/turns/{unanswered['turn_id']}/retry"
    header = {"X-User-Id": str(user_id)}

    # Chat is set up later; the model call fails once, then succeeds.
    monkeypatch.setenv("LLM_API_KEY", "test-key-not-real")
    monkeypatch.setenv("CHAT_MODEL", "test-chat-model")
    monkeypatch.setenv("CHAT_PRICE_IN", "2")
    monkeypatch.setenv("CHAT_PRICE_OUT", "10")
    get_settings.cache_clear()
    _use_answerer(monkeypatch, RuntimeError("upstream timed out"))
    assert client.post(retry_path, headers=header).status_code == 202
    [failed] = _settled(client, unanswered["thread_id"])["turns"]
    assert failed["status"] == "failed"
    assert "RuntimeError" in failed["error"] and "upstream" not in failed["error"]

    _use_answerer(monkeypatch, llm.ModelsNotConfigured("off"))
    assert client.post(retry_path, headers=header).status_code == 202
    [off] = _settled(client, unanswered["thread_id"])["turns"]
    assert off["status"] == "no_model"

    bill = _fact(seeded, FactKind.MEDICAL_BILL, ORTHO_ID)
    _use_answerer(monkeypatch, _citing(("Billed $2,480.", [bill.id])))
    assert client.post(retry_path, headers=header).status_code == 202
    [done] = _settled(client, unanswered["thread_id"])["turns"]
    assert done["status"] == "done" and done["turn_id"] == unanswered["turn_id"]

    assert client.post(retry_path, headers=header).status_code == 409


def test_an_answer_that_failed_upstream_keeps_its_reason(
    chat_on: None,
    seeded: Session,
    client: TestClient,
    user_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failed(session: Session, chat_input: ChatInput) -> ChatAnswer:
        return ChatAnswer(
            sentences=[],
            no_answer=False,
            dropped=0,
            llm_call_id=_paid_call(session, cost=0),
            error="The model did not answer (HTTP 529)",
        )

    _use_answerer(monkeypatch, failed)
    turn = _ask(client, user_id).json()

    [settled] = _settled(client, turn["thread_id"])["turns"]

    assert settled["status"] == "failed"
    assert settled["error"] == "The model did not answer (HTTP 529)"
    assert settled["sentences"] == []


# --- Closing a thread (D52) ---------------------------------------------------------------


def _close(
    client: TestClient, user_id: int, thread_id: int, matter_id: int = MATTER_ID
) -> Any:
    return client.post(
        f"/api/matters/{matter_id}/chat/threads/{thread_id}/close",
        headers={"X-User-Id": str(user_id)},
    )


def test_a_closed_thread_takes_no_question_or_retry_and_closing_again_changes_nothing(
    chat_on: None,
    seeded: Session,
    client: TestClient,
    user_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_answerer(monkeypatch, RuntimeError("upstream timed out"))
    turn = _ask(client, user_id).json()
    [failed] = _settled(client, turn["thread_id"])["turns"]
    assert failed["status"] == "failed"  # so only the closing stops a retry

    closed = _close(client, user_id, turn["thread_id"])

    assert closed.status_code == 200, closed.text
    thread = closed.json()
    assert thread["closed_at"] is not None
    assert thread["closed_by"] == seeded.get(User, user_id).name
    assert thread["turns"] == [failed]
    turns_before = _count(seeded, ChatTurn)
    asked = _ask(
        client, user_id, question="Anything else?", thread_id=turn["thread_id"]
    )
    assert asked.status_code == 409
    retried = client.post(
        f"/api/matters/{MATTER_ID}/chat/turns/{turn['turn_id']}/retry",
        headers={"X-User-Id": str(user_id)},
    )
    assert retried.status_code == 409
    assert _count(seeded, ChatTurn) == turns_before
    # Closing a closed thread returns it as it was, whoever asks.
    other_user = seeded.scalars(select(User.id).where(User.id != user_id)).first()
    again = _close(client, other_user or user_id, turn["thread_id"])
    assert again.status_code == 200 and again.json() == thread


def test_a_thread_with_a_running_turn_cannot_be_closed(
    chat_on: None,
    seeded: Session,
    client: TestClient,
    user_id: int,
    no_start: list[int],
) -> None:
    turn = _ask(client, user_id).json()
    assert turn["status"] == "running"

    assert _close(client, user_id, turn["thread_id"]).status_code == 409

    thread = client.get(f"/api/matters/{MATTER_ID}/chat/threads/{turn['thread_id']}")
    assert thread.json()["closed_at"] is None


def test_the_list_holds_open_threads_by_activity_then_closed_ones_by_closing_time(
    chat_off: None, seeded: Session, client: TestClient, user_id: int
) -> None:
    ids = [
        _ask(client, user_id, question=f"Question {n}?").json()["thread_id"]
        for n in range(4)
    ]
    first, second, third, fourth = ids
    start = datetime(2026, 3, 2, 9, 0, tzinfo=UTC)
    for minutes, thread_id in enumerate(ids):
        thread = seeded.get(ChatThread, thread_id)
        assert thread is not None
        thread.updated_at = start + timedelta(minutes=minutes)
    seeded.commit()
    user = seeded.get(User, user_id)
    assert user is not None
    # The first thread is closed last, so it leads the closed ones.
    chat.close(seeded, MATTER_ID, third, user, start + timedelta(hours=1))
    chat.close(seeded, MATTER_ID, first, user, start + timedelta(hours=2))

    listed = client.get(f"/api/matters/{MATTER_ID}/chat/threads").json()

    assert [t["thread_id"] for t in listed] == [fourth, second, first, third]
    assert [t["closed_at"] is not None for t in listed] == [False, False, True, True]


def test_a_closed_threads_transcript_downloads_as_text_with_each_sentence_sourced(
    chat_on: None,
    seeded: Session,
    client: TestClient,
    user_id: int,
    monkeypatch: pytest.MonkeyPatch,
    other_matter: dict[str, int],
) -> None:
    bill = _fact(seeded, FactKind.MEDICAL_BILL, ORTHO_ID)
    lien = _fact(seeded, FactKind.LIEN)
    _use_answerer(
        monkeypatch,
        _citing(
            ("The orthopedic office billed $2,480.", [bill.id]),
            ("A lien is on file.", [lien.id, bill.id]),
            ("The file does not say whether the bill was paid.", []),
        ),
    )
    turn = _ask(
        client, user_id, items=[{"kind": "facts", "fact_ids": [bill.id]}]
    ).json()
    _settled(client, turn["thread_id"])
    path = f"/api/matters/{MATTER_ID}/chat/threads/{turn['thread_id']}/transcript"
    assert client.get(path).status_code == 404  # open: nothing frozen yet

    thread = _close(client, user_id, turn["thread_id"]).json()
    response = client.get(path)

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert response.headers["content-disposition"] == (
        f'attachment; filename="clarity-thread-{turn["thread_id"]}.txt"'
    )
    text = response.text
    [frozen] = thread["turns"]
    # The bill's second read disagreed, so its chip is dashed and the transcript says so.
    assert bill.confidence is Confidence.LOW
    bill_source = f"{source_name(bill.source, bill.page_no)} (low confidence)"
    lien_source = source_name(lien.source, lien.page_no)
    assert "Matter: 00001-Avery" in text
    assert f"Thread: {thread['title']}" in text
    assert f"Closed by {thread['closed_by']}," in text
    assert f"asked by {frozen['asked_by']}," in text
    assert "What has the provider billed?" in text
    assert f"Pointed at: {frozen['items'][0]['label']}" in text
    assert f"- The orthopedic office billed $2,480. [{bill_source}]" in text
    assert f"- A lien is on file. [{lien_source}; {bill_source}]" in text
    assert (
        "- The file does not say whether the bill was paid. [the file does not say]"
        in text
    )
    assert "Cost: under $0.01" in text  # 1,234 micro-dollars
    other = f"/api/matters/{OTHER_MATTER}/chat/threads/{turn['thread_id']}/transcript"
    assert client.get(other).status_code == 404


def test_cost_reports_chat_apart_from_the_digest(
    seeded: Session, client: TestClient
) -> None:
    _paid_call(seeded, cost=7_000)
    seeded.add(
        LlmCall(
            matter_id=MATTER_ID,
            purpose="extract_page",
            model="m",
            cache_key="digest",
            cost_micro_usd=3_000,
        )
    )
    seeded.commit()

    cost = client.get(f"/api/ops/cost?matter_id={MATTER_ID}").json()

    assert (cost["model_calls"], cost["cost_micro_usd"]) == (1, 3_000)
    assert (cost["chat_calls"], cost["chat_cost_micro_usd"]) == (1, 7_000)


# --- Search -------------------------------------------------------------------------------


def test_search_finds_facts_at_word_starts_one_row_per_finding(
    seeded: Session, client: TestClient
) -> None:
    rows = client.get(f"/api/matters/{MATTER_ID}/search", params={"q": "lien"}).json()

    assert rows and rows[0]["kind"] == "lien"
    # "client" holds "lien", but not at a word start.
    for row in rows:
        text = f"{row['title']} {row['quote'] or ''}".lower()
        assert " lien" in f" {text}" or "\nlien" in text

    ranked = client.get(
        f"/api/matters/{MATTER_ID}/search", params={"q": "orthopedic", "limit": 2}
    ).json()
    assert len(ranked) == 2
    assert all("restated_by" in row for row in ranked)


def test_search_needs_two_characters(seeded: Session, client: TestClient) -> None:
    base = f"/api/matters/{MATTER_ID}/search"
    assert client.get(base, params={"q": "l"}).status_code == 422
    assert client.get(base, params={"q": "li", "limit": 21}).status_code == 422
    assert client.get(base, params={"q": "zzzz"}).json() == []
