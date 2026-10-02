"""Firm-view routes for a matter: header, brief, changes, feed, timeline, actions,
injuries, and the user list. Owned by Track B; queries live in
`services/matter_queries.py`."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import SessionDep
from app.models import FactKind
from app.schemas import ActionsOut, FactOut, MatterHeaderOut, MatterSummaryOut
from app.services import matter_queries

router = APIRouter(prefix="/api", tags=["matters"])


def _existing_matter(matter_id: int, session: SessionDep) -> int:
    if not matter_queries.matter_exists(session, matter_id):
        raise HTTPException(status_code=404, detail=f"Matter {matter_id} not found")
    return matter_id


MatterId = Annotated[int, Depends(_existing_matter)]


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
