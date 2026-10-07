"""Calls placed from Clarity (docs/calls-contract.md). Firm routes only: no provider
route returns a call or a note. Handlers call `services/calls.py` and
`services/call_targets.py`; ending a call starts its notes in the background."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.db import SessionDep
from app.schemas import (
    CallDetailOut,
    CallNumberIn,
    CallOut,
    CallStartIn,
    CallTargetOut,
    CallTranscriptIn,
)
from app.services import call_targets, calls, matter_queries

router = APIRouter(prefix="/api", tags=["calls"])


def _existing_matter(matter_id: int, session: SessionDep) -> int:
    if not matter_queries.matter_exists(session, matter_id):
        raise HTTPException(status_code=404, detail=f"Matter {matter_id} not found")
    return matter_id


MatterId = Annotated[int, Depends(_existing_matter)]


@router.get("/matters/{matter_id}/calls/next")
def next_calls(matter_id: MatterId, session: SessionDep) -> list[CallTargetOut]:
    return call_targets.call_targets(session, matter_id, datetime.now(UTC).date())


@router.post("/matters/{matter_id}/call-numbers", status_code=201)
def add_call_number(
    matter_id: MatterId, body: CallNumberIn, session: SessionDep
) -> CallTargetOut:
    """A typed name and number, stored in Clarity only (D15)."""
    return call_targets.add_number(
        session, matter_id, body.name, body.phone, datetime.now(UTC).date()
    )


@router.post("/matters/{matter_id}/calls", status_code=201)
def start_call(matter_id: MatterId, body: CallStartIn, session: SessionDep) -> CallOut:
    try:
        return calls.start_call(
            session,
            matter_id,
            body.target_id,
            body.consent_confirmed,
            body.consent_text,
            datetime.now(UTC),
        )
    except calls.ConsentRequired as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except call_targets.UnknownTarget as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/matters/{matter_id}/calls")
def list_calls(matter_id: MatterId, session: SessionDep) -> list[CallOut]:
    return calls.list_calls(session, matter_id)


@router.put("/calls/{call_id}/transcript")
def save_transcript(
    call_id: int, body: CallTranscriptIn, session: SessionDep
) -> CallOut:
    try:
        return calls.save_transcript(session, call_id, body.text, body.final)
    except calls.CallNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except calls.TranscriptClosed as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/calls/{call_id}/end")
def end_call(call_id: int, session: SessionDep) -> CallOut:
    try:
        return calls.end_call(session, call_id, datetime.now(UTC))
    except calls.CallNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/calls/{call_id}")
def call_detail(call_id: int, session: SessionDep) -> CallDetailOut:
    try:
        return calls.call_detail(session, call_id)
    except calls.CallNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
