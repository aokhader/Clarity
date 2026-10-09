"""The chatbot's routes (D49, docs/chat-contract.md). Firm routes only: nothing under
`/api/p` reaches a thread, a turn or the search.

No handler calls a model. `POST chat/ask` and `POST chat/turns/{id}/retry` store the
turn and start its answer in the background (`services/chat.py`); the UI polls the
thread. Handlers call `services/chat.py` and `services/chat_context.py`.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response

from app.api.matters import CurrentUser, MatterId
from app.db import SessionDep
from app.schemas import (
    ChatAskIn,
    ChatBudgetOut,
    ChatThreadOut,
    ChatThreadSummaryOut,
    ChatTurnOut,
    FactOut,
)
from app.services import chat, chat_context, chat_view
from app.services.chat_attachments import ItemNotInMatter

router = APIRouter(prefix="/api/matters/{matter_id}", tags=["chat"])


@router.post("/chat/ask", status_code=202)
def ask(
    matter_id: MatterId, body: ChatAskIn, user: CurrentUser, session: SessionDep
) -> ChatTurnOut:
    try:
        return chat.ask(session, matter_id, user, body, datetime.now(UTC))
    except chat.ChatOverBudget as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    except chat.ThreadNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except chat.TurnConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ItemNotInMatter as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/chat/threads")
def list_threads(
    matter_id: MatterId, session: SessionDep
) -> list[ChatThreadSummaryOut]:
    return chat_view.thread_summaries(session, matter_id)


@router.get("/chat/threads/{thread_id}")
def get_thread(
    matter_id: MatterId, thread_id: int, session: SessionDep
) -> ChatThreadOut:
    try:
        return chat.get_thread(session, matter_id, thread_id)
    except chat.ThreadNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/chat/turns/{turn_id}/retry", status_code=202)
def retry_turn(
    matter_id: MatterId, turn_id: int, _user: CurrentUser, session: SessionDep
) -> ChatTurnOut:
    try:
        return chat.retry(session, matter_id, turn_id, datetime.now(UTC))
    except chat.TurnNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except chat.TurnConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except chat.ChatOverBudget as error:
        raise HTTPException(status_code=429, detail=str(error)) from error


@router.post("/chat/threads/{thread_id}/archive", status_code=204)
def archive_thread(
    matter_id: MatterId, thread_id: int, _user: CurrentUser, session: SessionDep
) -> Response:
    try:
        chat.archive(session, matter_id, thread_id, datetime.now(UTC))
    except chat.ThreadNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return Response(status_code=204)


@router.get("/chat/budget")
def chat_budget(matter_id: MatterId, session: SessionDep) -> ChatBudgetOut:
    return chat.budget(session, matter_id, datetime.now(UTC))


@router.get("/search")
def search(
    matter_id: MatterId,
    session: SessionDep,
    q: Annotated[str, Query(min_length=2, max_length=200)],
    limit: Annotated[int, Query(ge=1, le=20)] = 12,
) -> list[FactOut]:
    return chat_context.search_facts(session, matter_id, q, limit)
