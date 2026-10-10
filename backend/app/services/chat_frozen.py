"""A closed thread's cited sources, frozen when it closed (D54, docs/chat-contract.md).

A closed thread is the firm's record of what was cited. Its chips are fact ids, and a
re-read replaces fact ids, so a chip could open nothing, or another fact that took the
same id. Closing therefore stores, for every fact the frozen turns cite (sentence
chips, figure marks and item chips), the drawer's `FactSourceOut` as it was served
then, its pages cut to the cited page. The frozen route serves that copy. Page image
URLs still point at the live file; the text is what was frozen.

A thread closed before D54 has no copies: one is built the first time a chip is opened,
if the cited fact still exists. Nothing here calls a model.
"""

import logging
from collections.abc import Iterable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import ChatFrozenSource, ChatThread, Fact
from app.schemas import ChatTurnOut, FactRef, FactSourceOut
from app.services import source_views

log = logging.getLogger(__name__)

GONE = "This source is no longer in the file."


class FrozenSourceNotFound(LookupError):
    """The thread is not a closed thread of this matter, or it does not cite the fact,
    or a thread closed before D54 cites a fact that is gone (404)."""


def cited_refs(turns: Iterable[ChatTurnOut]) -> dict[int, FactRef]:
    """Every fact a chip of the turns opens, by id, in the order first cited: each
    sentence's chips and its figure marks' chips (a "differs" mark cites the file's
    figure), then each item's."""
    refs: dict[int, FactRef] = {}
    for turn in turns:
        for sentence in turn.sentences:
            for ref in sentence.facts:
                refs.setdefault(ref.id, ref)
            for mention in sentence.mentions:
                for ref in mention.facts:
                    refs.setdefault(ref.id, ref)
        for item in turn.items:
            for ref in item.facts:
                refs.setdefault(ref.id, ref)
    return refs


def freeze(session: Session, thread: ChatThread, turns: list[ChatTurnOut]) -> int:
    """Store a copy of every source the turns cite, in the caller's transaction (the
    close). Returns the number stored."""
    stored = 0
    for fact_id in cited_refs(turns):
        try:
            copy = _served_now(session, fact_id)
        except source_views.FactNotFound:
            # The live turns cite only renderable facts, so this is not expected.
            log.warning("Chat thread %d: fact %d not frozen", thread.id, fact_id)
            continue
        session.add(_row(thread.id, fact_id, copy))
        stored += 1
    return stored


def frozen_source(
    session: Session, matter_id: int, thread_id: int, fact_id: int
) -> FactSourceOut:
    """The source a closed thread's chip opens, as it was when the thread closed."""
    thread = session.get(ChatThread, thread_id)
    if thread is None or thread.matter_id != matter_id:
        raise FrozenSourceNotFound(f"thread {thread_id} is not in matter {matter_id}")
    if thread.transcript is None:
        raise FrozenSourceNotFound(f"thread {thread_id} is open; nothing is frozen")
    turns = (ChatTurnOut.model_validate(t) for t in thread.transcript.turns_json)
    ref = cited_refs(turns).get(fact_id)
    if ref is None:
        raise FrozenSourceNotFound(f"thread {thread_id} does not cite fact {fact_id}")
    row = session.get(ChatFrozenSource, (thread_id, fact_id))
    if row is not None:
        return FactSourceOut.model_validate(row.source_json)
    return _backfill(session, thread, ref)


def _backfill(session: Session, thread: ChatThread, ref: FactRef) -> FactSourceOut:
    """Freeze the source of a thread closed before D54, if the cited fact is still the
    one in the file: same matter, same kind of record, same page. An id that a re-read
    gave to another fact is not what was cited."""
    try:
        copy = _served_now(session, ref.id)
    except source_views.FactNotFound as error:
        raise FrozenSourceNotFound(GONE) from error
    fact = session.get(Fact, ref.id)
    same = (
        fact is not None
        and fact.matter_id == thread.matter_id
        and copy.source.source_type == ref.source_type
        and fact.page_no == ref.page_no
    )
    if not same:
        raise FrozenSourceNotFound(GONE)
    session.add(_row(thread.id, ref.id, copy))
    try:
        session.commit()
    except IntegrityError:
        # Another request froze it first; serve the copy it stored.
        session.rollback()
        row = session.get(ChatFrozenSource, (thread.id, ref.id))
        if row is None:
            raise
        return FactSourceOut.model_validate(row.source_json)
    log.info("Chat thread %d: fact %d frozen on first open", thread.id, ref.id)
    return copy


def _served_now(session: Session, fact_id: int) -> FactSourceOut:
    """The drawer's answer for the fact today (`GET /api/facts/{id}/source`), with the
    source's pages cut to the fact's own page; all of them when it has none."""
    served = source_views.fact_source(session, fact_id)
    page_no = served.fact.page_no
    if page_no is None:
        return served
    pages = [p for p in served.source.pages if p.page_no == page_no]
    return served.model_copy(
        update={"source": served.source.model_copy(update={"pages": pages})}
    )


def _row(thread_id: int, fact_id: int, copy: FactSourceOut) -> ChatFrozenSource:
    return ChatFrozenSource(
        thread_id=thread_id, fact_id=fact_id, source_json=copy.model_dump(mode="json")
    )
