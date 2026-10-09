"""Questions to the chatbot and their background runs (D49).

`ask` and `retry` store a turn and return at once; the answer is made in a daemon
thread with its own session (the call-notes pattern), so no request waits on a model
and no GET calls one. The thread builds the context in code (`chat_context.py`), calls
pipeline's `answer_question` once, and stores the checked sentences with the fact ids
each cites. Verdicts are not stored: `chat_view.py` computes them when a turn is served.

Closing a thread (D52) freezes its turns as served at that moment, with a plain-text
transcript (`chat_transcript.py`), and ends it: no question or retry is taken after.

Spend is capped per matter per local day, summed from `llm_calls` with purpose `chat`.
Logs carry counts and ids only, never a question or record text (rule 7).
"""

import logging
import threading
from collections.abc import Callable
from datetime import datetime, time, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_sessionmaker
from app.models import ChatStatus, ChatThread, ChatTranscript, ChatTurn, User, utcnow
from app.schemas import ChatAskIn, ChatBudgetOut, ChatThreadOut, ChatTurnOut
from app.services import chat_view
from app.services.chat_attachments import load_renderable, resolve_items
from app.services.chat_context import build_context, context_fact_ids, prior_turns
from app.services.chat_transcript import transcript_text
from app.services.cost import chat_spent_since

log = logging.getLogger(__name__)

TITLE_CHARS = 80
INTERRUPTED = "Interrupted; ask again"
# Same bound as the run rows' `error` column.
MAX_ERROR_CHARS = 2000
_RETRYABLE = (ChatStatus.FAILED, ChatStatus.NO_MODEL)

Answerer = Callable[..., Any]


class ChatOverBudget(Exception):
    """The matter's chat spend today has reached the cap (429)."""


class ThreadNotFound(LookupError):
    """No such thread in this matter (404)."""


class TurnNotFound(LookupError):
    """No such turn in this matter (404)."""


class TurnConflict(Exception):
    """A turn of the thread is running, the thread is closed, or the turn cannot be
    retried (409)."""


class TranscriptNotFound(LookupError):
    """The thread is open, so it has no transcript yet (404)."""


# --- Spend -----------------------------------------------------------------------------


def local_day(now: datetime) -> tuple[datetime, datetime]:
    """The server's local midnight before `now` and the next, timezone-aware.

    Each is built from the local calendar day, so a day with a clock change still
    starts and ends at midnight. Stored times are UTC; comparing aware values is exact.
    """
    day = now.astimezone().date()
    start = datetime.combine(day, time()).astimezone()
    end = datetime.combine(day + timedelta(days=1), time()).astimezone()
    return start, end


def budget(session: Session, matter_id: int, now: datetime) -> ChatBudgetOut:
    settings = get_settings()
    start, end = local_day(now)
    return ChatBudgetOut(
        spent_today_micro_usd=chat_spent_since(session, matter_id, start),
        cap_micro_usd=int(settings.chat_daily_budget_usd * 1_000_000),
        resets_at=end,
        configured=settings.chat_configured,
    )


def _check_budget(session: Session, matter_id: int, now: datetime) -> None:
    today = budget(session, matter_id, now)
    if today.spent_today_micro_usd >= today.cap_micro_usd:
        raise ChatOverBudget(
            "Today's chat budget for this matter is spent; it resets at midnight"
        )


# --- Asking ----------------------------------------------------------------------------


def ask(
    session: Session, matter_id: int, user: User, body: ChatAskIn, now: datetime
) -> ChatTurnOut:
    """Store the question as a new turn and start its answer. Creates nothing when it
    raises: ChatOverBudget, ThreadNotFound, TurnConflict, or ItemNotInMatter."""
    _check_budget(session, matter_id, now)
    thread = None
    if body.thread_id is not None:
        thread = _thread(session, matter_id, body.thread_id)
        _still_open(thread)
        _no_running_turn(session, thread.id)
    # Every item must resolve in this matter before anything is stored.
    resolve_items(session, matter_id, list(body.items))
    if thread is None:
        thread = ChatThread(
            matter_id=matter_id,
            created_by=user.id,
            title=body.question[:TITLE_CHARS],
            created_at=now,
        )
        session.add(thread)
    thread.updated_at = now
    configured = get_settings().chat_configured
    turn = ChatTurn(
        thread=thread,
        matter_id=matter_id,
        asked_by=user.id,
        question=body.question,
        items_json=[ref.model_dump(mode="json") for ref in body.items],
        status=ChatStatus.RUNNING if configured else ChatStatus.NO_MODEL,
        created_at=now,
    )
    session.add(turn)
    session.commit()
    log.info(
        "Chat turn %d in thread %d for matter %d: %d items, %s",
        turn.id,
        thread.id,
        matter_id,
        len(body.items),
        turn.status.value,
    )
    if configured:
        start(turn.id)
    return chat_view.single_turn_out(session, turn)


def retry(session: Session, matter_id: int, turn_id: int, now: datetime) -> ChatTurnOut:
    """Ask a failed or unanswered turn again, in place."""
    turn = session.get(ChatTurn, turn_id)
    if turn is None or turn.matter_id != matter_id:
        raise TurnNotFound(f"turn {turn_id} is not in matter {matter_id}")
    _still_open(turn.thread)
    if turn.status not in _RETRYABLE:
        raise TurnConflict("Only a failed or unanswered turn can be asked again")
    _no_running_turn(session, turn.thread_id)
    _check_budget(session, matter_id, now)
    configured = get_settings().chat_configured
    turn.status = ChatStatus.RUNNING if configured else ChatStatus.NO_MODEL
    turn.answer_json = None
    turn.context_fact_ids_json = None
    turn.llm_call_id = None
    turn.error = None
    turn.finished_at = None
    turn.thread.updated_at = now
    session.commit()
    log.info("Chat turn %d retried: %s", turn.id, turn.status.value)
    if configured:
        start(turn.id)
    return chat_view.single_turn_out(session, turn)


def get_thread(session: Session, matter_id: int, thread_id: int) -> ChatThreadOut:
    return chat_view.thread_out(session, _thread(session, matter_id, thread_id))


def close(
    session: Session, matter_id: int, thread_id: int, user: User, now: datetime
) -> ChatThreadOut:
    """Close the thread (D52): freeze its turns as served now, with a text transcript,
    and take no more questions in it. A closed thread comes back unchanged. Raises
    ThreadNotFound, or TurnConflict while a turn is running."""
    thread = _thread(session, matter_id, thread_id)
    if thread.transcript is None:
        _no_running_turn(session, thread.id)
        turns = chat_view.live_turns(session, thread)
        thread.closed_at = now
        thread.transcript = ChatTranscript(
            closed_by=user.id,
            closed_at=now,
            turns_json=[t.model_dump(mode="json") for t in turns],
            text=transcript_text(session, thread, turns, user.name, now),
        )
        session.commit()
        log.info("Chat thread %d closed with %d turns", thread.id, len(turns))
    return chat_view.thread_out(session, thread)


def transcript(session: Session, matter_id: int, thread_id: int) -> str:
    """The text transcript frozen when the thread closed. Raises ThreadNotFound, or
    TranscriptNotFound while the thread is open."""
    thread = _thread(session, matter_id, thread_id)
    if thread.transcript is None:
        raise TranscriptNotFound(f"thread {thread_id} is open; it has no transcript")
    return thread.transcript.text


def _thread(session: Session, matter_id: int, thread_id: int) -> ChatThread:
    thread = session.get(ChatThread, thread_id)
    if thread is None or thread.matter_id != matter_id:
        raise ThreadNotFound(f"thread {thread_id} is not in matter {matter_id}")
    return thread


def _still_open(thread: ChatThread) -> None:
    if thread.transcript is not None:
        raise TurnConflict("This thread is closed; ask in a new thread")


def _no_running_turn(session: Session, thread_id: int) -> None:
    running = session.scalar(
        select(ChatTurn.id).where(
            ChatTurn.thread_id == thread_id, ChatTurn.status == ChatStatus.RUNNING
        )
    )
    if running is not None:
        raise TurnConflict("This thread is still answering a question")


# --- The background run ----------------------------------------------------------------


def start(turn_id: int) -> None:
    """Answer the turn in a background thread with its own session."""

    def target() -> None:
        try:
            with get_sessionmaker()() as session:
                run_turn(session, turn_id)
        except Exception as error:
            # Left running; the startup sweep marks it failed. The type only (rule 7).
            log.error(
                "Chat turn %d: the run stopped: %s", turn_id, type(error).__name__
            )
            log.debug("Chat turn %d: the run stopped", turn_id, exc_info=True)

    threading.Thread(target=target, daemon=True, name=f"chat-turn-{turn_id}").start()


def run_turn(session: Session, turn_id: int) -> None:
    """Build the context, ask once, store the checked answer; record any failure on
    the turn, so its status never stays running."""
    from app.digest.llm import ModelsNotConfigured

    turn = session.get(ChatTurn, turn_id)
    if turn is None or turn.status is not ChatStatus.RUNNING:
        return
    matter_id, question = turn.matter_id, turn.question
    settings = get_settings()
    try:
        answer_question = _answerer()
        renderable = load_renderable(session, matter_id)
        items = resolve_items(
            session,
            matter_id,
            chat_view.stored_refs(turn),
            renderable=renderable,
            page_chars=settings.chat_page_chars,
            page_limit=settings.chat_context_pages,
        )
        chat_input = build_context(
            session,
            matter_id,
            question,
            items,
            prior_turns(session, turn, renderable),
            renderable=renderable,
        )
        shown_ids = context_fact_ids(chat_input)
        answer = answer_question(
            session, matter_id=matter_id, question=question, chat_input=chat_input
        )
    except ModelsNotConfigured:
        session.rollback()
        _finish(session, turn_id, ChatStatus.NO_MODEL, None)
        return
    except Exception as error:
        # The type only: an exception's message can carry record text (rule 7).
        log.warning("Chat turn %d failed: %s", turn_id, type(error).__name__)
        log.debug("Chat turn %d failure", turn_id, exc_info=True)
        session.rollback()
        _finish(
            session,
            turn_id,
            ChatStatus.FAILED,
            f"The answer could not be made ({type(error).__name__}); ask again",
        )
        return

    turn = session.get(ChatTurn, turn_id)
    if turn is None:
        return
    turn.context_fact_ids_json = shown_ids
    turn.llm_call_id = answer.llm_call_id
    if answer.error:
        turn.status = ChatStatus.FAILED
        turn.error = answer.error[:MAX_ERROR_CHARS]
    else:
        turn.status = ChatStatus.DONE
        turn.answer_json = {
            "sentences": [
                {
                    "text": s.text,
                    "fact_ids": list(s.fact_ids),
                    "not_in_file": s.not_in_file,
                }
                for s in answer.sentences
            ],
            "no_answer": answer.no_answer,
            "dropped": answer.dropped,
        }
    turn.finished_at = utcnow()
    turn.thread.updated_at = turn.finished_at
    session.commit()
    log.info(
        "Chat turn %d: %s, %d sentences, %d dropped, %d facts shown, llm call %s",
        turn_id,
        turn.status.value,
        len(answer.sentences),
        answer.dropped,
        len(shown_ids),
        answer.llm_call_id,
    )


def _finish(
    session: Session, turn_id: int, status: ChatStatus, error: str | None
) -> None:
    turn = session.get(ChatTurn, turn_id)
    if turn is None:
        return
    turn.status = status
    turn.error = error
    turn.finished_at = utcnow()
    turn.thread.updated_at = turn.finished_at
    session.commit()


def fail_interrupted_turns(session: Session) -> int:
    """Mark turns left running by a stopped server as failed (called at startup), so a
    reload cannot leave a turn running forever."""
    result = session.execute(
        update(ChatTurn)
        .where(ChatTurn.status == ChatStatus.RUNNING)
        .values(status=ChatStatus.FAILED, error=INTERRUPTED, finished_at=utcnow())
    )
    session.commit()
    count = result.rowcount or 0
    if count:
        log.info("Marked %d interrupted chat turns as failed", count)
    return count


def _answerer() -> Answerer:
    """Pipeline's `answer_question`, imported when a run starts."""
    from app.digest.chat import answer_question

    return answer_question
