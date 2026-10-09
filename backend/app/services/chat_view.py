"""Chat turns and threads as the firm sees them (D49), recomputed each time they are served.

A turn stores its sentences and the fact ids each cites, never a verdict. When it is
served:

- a sentence citing a fact that can no longer be shown is withdrawn and counted, the
  rule the brief follows (`brief_view.py`), since part of what it says would be on
  screen without a source;
- every other sentence's amounts and dates are checked against today's file
  (`brief_check.check_sentence`, D12), so an answer given before a correction says so;
- a figure the check finds supported only by facts the sentence does not cite adds
  those facts' chips after the cited ones (D50), so every figure on screen has a chip
  whose source holds it (rule 3);
- the items are resolved again for their labels and facts. One that no longer
  resolves keeps a generic label and no facts rather than failing the thread.
"""

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
    DraftMentionOut,
    FactRef,
)
from app.services.brief_check import check_sentence, figures_stated_by, file_values
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
        ids = sentence.get("fact_ids", [])
        if not ids or not all(i in renderable for i in ids):
            withdrawn += 1
            continue
        cited = [renderable[i] for i in ids]
        verdict, mentions = check_sentence(text, cited, file)
        sentences.append(
            ChatSentenceOut(
                text=text,
                facts=_chips(text, cited, mentions, renderable),
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


def _chips(
    text: str,
    cited: list[Fact],
    mentions: list[DraftMentionOut],
    renderable: dict[int, Fact],
) -> list[FactRef]:
    """The sentence's cited facts, then, for each supported figure no cited fact
    states, the facts that state it, each fact once.

    A figure that matches a computed total is supported by every fact the total adds
    up, and none of those records states the total; a provider's bills can be a
    hundred facts. So the facts that state the figure themselves are preferred, and the
    total's facts are added only when no fact does."""
    chips = {f.id: fact_ref(f) for f in cited}
    uncovered = [
        m
        for m in mentions
        if m.verdict == "supported" and not any(r.id in chips for r in m.facts)
    ]
    if not uncovered:
        return list(chips.values())
    behind = [
        renderable[r.id] for m in uncovered for r in m.facts if r.id in renderable
    ]
    stated = figures_stated_by(text, behind)
    for mention in uncovered:
        for ref in stated.get((mention.start, mention.end)) or mention.facts:
            chips.setdefault(ref.id, ref)
    return list(chips.values())


def thread_out(session: Session, thread: ChatThread) -> ChatThreadOut:
    renderable = load_renderable(session, thread.matter_id)
    file = file_values(list(renderable.values()))
    return ChatThreadOut(
        thread_id=thread.id,
        title=thread.title,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        turns=[turn_out(session, t, renderable, file) for t in thread.turns],
    )


def single_turn_out(session: Session, turn: ChatTurn) -> ChatTurnOut:
    """One turn, as `POST ask` and `retry` return it."""
    renderable = load_renderable(session, turn.matter_id)
    file = file_values(list(renderable.values())) if turn.answer_json else []
    return turn_out(session, turn, renderable, file)


def thread_summaries(session: Session, matter_id: int) -> list[ChatThreadSummaryOut]:
    """The matter's threads that are not archived, the most recently active first."""
    threads = session.scalars(
        select(ChatThread)
        .options(selectinload(ChatThread.turns))
        .where(ChatThread.matter_id == matter_id, ChatThread.archived_at.is_(None))
        .order_by(ChatThread.updated_at.desc(), ChatThread.id.desc())
    ).all()
    return [
        ChatThreadSummaryOut(
            thread_id=t.id,
            title=t.title,
            updated_at=t.updated_at,
            turn_count=len(t.turns),
            last_status=t.turns[-1].status.value,
            asked_by=_user_name(session, t.created_by),
        )
        for t in threads
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
