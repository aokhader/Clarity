"""Firm-view routes for a matter: header, brief, changes, feed, timeline, actions,
injuries, and the user list. Owned by Track B; queries live in
`services/matter_queries.py`."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.db import SessionDep
from app.models import FactKind, User
from app.schemas import (
    ActionsOut,
    BriefOut,
    ChangesOut,
    FactOut,
    MatterHeaderOut,
    MatterSummaryOut,
    OpenedOut,
    UserOut,
)
from app.services import brief_view, matter_queries, users, visits

router = APIRouter(prefix="/api", tags=["matters"])


def _existing_matter(matter_id: int, session: SessionDep) -> int:
    if not matter_queries.matter_exists(session, matter_id):
        raise HTTPException(status_code=404, detail=f"Matter {matter_id} not found")
    return matter_id


def _current_user(
    session: SessionDep, x_user_id: Annotated[int | None, Header()] = None
) -> User:
    # A stub account chosen by the header's user switcher; there is no real login.
    user = users.find_user(session, x_user_id) if x_user_id is not None else None
    if user is None:
        raise HTTPException(status_code=401, detail="Choose a firm user (X-User-Id)")
    return user


MatterId = Annotated[int, Depends(_existing_matter)]
CurrentUser = Annotated[User, Depends(_current_user)]


@router.get("/users")
def list_users(session: SessionDep) -> list[UserOut]:
    return users.list_users(session)


@router.get("/matters")
def list_matters(session: SessionDep) -> list[MatterSummaryOut]:
    return matter_queries.list_matters(session)


@router.get("/matters/{matter_id}")
def matter_header(matter_id: MatterId, session: SessionDep) -> MatterHeaderOut:
    return matter_queries.matter_header(session, matter_id)


@router.get("/matters/{matter_id}/actions")
def matter_actions(matter_id: MatterId, session: SessionDep) -> ActionsOut:
    today = datetime.now(UTC).date()
    return matter_queries.matter_actions(session, matter_id, today)


@router.get("/matters/{matter_id}/feed")
def matter_feed(
    matter_id: MatterId,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[FactOut]:
    return matter_queries.matter_feed(session, matter_id, limit)


@router.get("/matters/{matter_id}/timeline")
def matter_timeline(
    matter_id: MatterId,
    session: SessionDep,
    kind: FactKind | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> list[FactOut]:
    return matter_queries.matter_timeline(session, matter_id, kind, q)


@router.get("/matters/{matter_id}/brief")
def matter_brief(matter_id: MatterId, session: SessionDep) -> BriefOut:
    try:
        return brief_view.matter_brief(session, matter_id)
    except brief_view.BriefNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/matters/{matter_id}/injuries")
def matter_injuries(matter_id: MatterId, session: SessionDep) -> list[FactOut]:
    return matter_queries.matter_injuries(session, matter_id)


@router.get("/matters/{matter_id}/changes")
def matter_changes(
    matter_id: MatterId, user: CurrentUser, session: SessionDep
) -> ChangesOut:
    return visits.matter_changes(session, matter_id, user, datetime.now(UTC))


@router.post("/matters/{matter_id}/opened")
def record_visit(
    matter_id: MatterId, user: CurrentUser, session: SessionDep
) -> OpenedOut:
    return visits.record_visit(session, matter_id, user, datetime.now(UTC))
