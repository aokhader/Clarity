"""Chat turns and threads as the firm sees them (D49), recomputed each time they are served.

A turn stores its sentences and the fact ids each cites, never a verdict. When it is
served:

- a sentence citing a fact that can no longer be shown is withdrawn and counted, the
  rule the brief follows (`brief_view.py`), since part of what it says would be on
  screen without a source;
- every other sentence's amounts and dates are checked against today's file
  (`brief_check.check_sentence`, D12), so an answer given before a correction says so;
- a sentence's chips are the facts the model cited, in its order, and no others (D51).
  A figure that other records state keeps its verdict and names them in its mention,
  but adds no chip: a record that shares only a date or an amount with the sentence
  does not hold what it says;
- the items are resolved again for their labels and facts. One that no longer
  resolves keeps a generic label and no facts rather than failing the thread.

A closed thread (D52) is the exception: it is served from the copy frozen when it
closed (`ChatTranscript.turns_json`), never checked again, since it is the record of
what was said then.
"""

from datetime import datetime

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import ChatStatus, ChatThread, ChatTurn, Fact, LlmCall, User
from app.schemas import (
    AskItemOut,
    AskItemRef,
    ChatSentenceOut,
    ChatThreadOut,
    ChatThreadSummaryOut,
    ChatTurnOut,
)
from app.services.brief_check import check_sentence, file_values
from app.services.chat_attachments import (
    AskRef,
    ItemNotInMatter,
    fallback_label,
    load_renderable,
    resolve_items,
)
from app.services.fact_views import fact_ref
from app.services.known_values import KnownValue

_ITEM_REF: TypeAdapter[AskRef] = TypeAdapter(AskItemRef)


def stored_refs(turn: ChatTurn) -> list[AskRef]:
    """The item refs as the client sent them."""
    return [_ITEM_REF.validate_python(raw) for raw in turn.items_json]


def turn_out(
    session: Session,
    turn: ChatTurn,
    renderable: dict[int, Fact],
    file: list[KnownValue],
) -> ChatTurnOut:
    sentences: list[ChatSentenceOut] = []
    withdrawn = 0
    answer = turn.answer_json if turn.status is ChatStatus.DONE else None
    for sentence in (answer or {}).get("sentences", []):
        text = sentence["text"]
        if sentence.get("not_in_file"):
            # It says the file does not answer; it states no figure and cites nothing.
            sentences.append(
                ChatSentenceOut(
                    text=text,
                    facts=[],
                    verdict="unchecked",
                    mentions=[],
                    not_in_file=True,
                )
            )
            continue
        ids = list(dict.fromkeys(sentence.get("fact_ids", [])))
        if not ids or not all(i in renderable for i in ids):
            withdrawn += 1
            continue
        cited = [renderable[i] for i in ids]
        verdict, mentions = check_sentence(text, cited, file)
        sentences.append(
            ChatSentenceOut(
                text=text,
                facts=[fact_ref(f) for f in cited],
                verdict=verdict,
                mentions=mentions,
                not_in_file=False,
            )
        )
    return ChatTurnOut(
        turn_id=turn.id,
        thread_id=turn.thread_id,
        question=turn.question,
        items=_items(session, turn, renderable),
        status=turn.status.value,
        sentences=sentences,
        no_answer=bool((answer or {}).get("no_answer", False)),
        withdrawn=withdrawn,
        error=turn.error,
        cost_micro_usd=_cost(session, turn),
        asked_by=_user_name(session, turn.asked_by),
        asked_at=turn.created_at,
        answered_at=turn.finished_at,
    )


def live_turns(session: Session, thread: ChatThread) -> list[ChatTurnOut]:
    """The thread's turns checked against today's file, oldest first."""
    renderable = load_renderable(session, thread.matter_id)
    file = file_values(list(renderable.values()))
    return [turn_out(session, t, renderable, file) for t in thread.turns]


def thread_out(session: Session, thread: ChatThread) -> ChatThreadOut:
    """An open thread as served now; a closed one exactly as frozen when it closed."""
    frozen = thread.transcript
    if frozen is not None:
        turns = [ChatTurnOut.model_validate(t) for t in frozen.turns_json]
    else:
        turns = live_turns(session, thread)
    return ChatThreadOut(
        thread_id=thread.id,
        title=thread.title,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        turns=turns,
        closed_at=closed_at(thread),
        closed_by=_user_name(session, frozen.closed_by) if frozen else None,
    )


def closed_at(thread: ChatThread) -> datetime | None:
    """When the thread was closed. Only a frozen transcript makes a thread closed: one
    archived before D52 kept nothing, so it is served as open and can be closed."""
    return thread.closed_at if thread.transcript is not None else None


def single_turn_out(session: Session, turn: ChatTurn) -> ChatTurnOut:
    """One turn, as `POST ask` and `retry` return it."""
    renderable = load_renderable(session, turn.matter_id)
    file = file_values(list(renderable.values())) if turn.answer_json else []
    return turn_out(session, turn, renderable, file)


def thread_summaries(session: Session, matter_id: int) -> list[ChatThreadSummaryOut]:
    """Every thread of the matter: the open ones first, the most recently active first,
    then the closed ones, the most recently closed first (D52). A closed thread's turns
    no longer change, so its count and last status are those it closed with."""
    threads = session.scalars(
        select(ChatThread)
        .options(selectinload(ChatThread.turns), selectinload(ChatThread.transcript))
        .where(ChatThread.matter_id == matter_id)
    ).all()

    def newest_first(thread: ChatThread) -> tuple[bool, datetime, int]:
        closed = closed_at(thread)
        return (closed is None, closed or thread.updated_at, thread.id)

    return [
        ChatThreadSummaryOut(
            thread_id=t.id,
            title=t.title,
            updated_at=t.updated_at,
            turn_count=len(t.turns),
            last_status=t.turns[-1].status.value,
            asked_by=_user_name(session, t.created_by),
            closed_at=closed_at(t),
        )
        for t in sorted(threads, key=newest_first, reverse=True)
        if t.turns  # a thread is created with its first turn, in one commit
    ]


def _items(
    session: Session, turn: ChatTurn, renderable: dict[int, Fact]
) -> list[AskItemOut]:
    out = []
    for ref in stored_refs(turn):
        try:
            [item] = resolve_items(
                session, turn.matter_id, [ref], renderable=renderable
            )
        except ItemNotInMatter:
            out.append(AskItemOut(ref=ref, label=fallback_label(ref), facts=[]))
            continue
        out.append(
            AskItemOut(
                ref=ref, label=item.label, facts=[fact_ref(f) for f in item.facts]
            )
        )
    return out


def _cost(session: Session, turn: ChatTurn) -> int | None:
    """What the answer's model call cost; None while running or when it was cached."""
    if turn.status is ChatStatus.RUNNING or turn.llm_call_id is None:
        return None
    call = session.get(LlmCall, turn.llm_call_id)
    if call is None or call.cache_hit:
        return None
    return call.cost_micro_usd


def _user_name(session: Session, user_id: int | None) -> str | None:
    user = session.get(User, user_id) if user_id is not None else None
    return user.name if user is not None else None
