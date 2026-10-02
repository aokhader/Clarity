"""Share management and the providers panel, for firm users. Owned by Track C; the
visibility filter lives in `services/visibility.py`."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException

from app.db import SessionDep
from app.models import Share, User
from app.schemas import (
    ProviderOut,
    ShareCreate,
    ShareOut,
    SharePreviewOut,
    ShareUpdate,
)
from app.services import matter_queries, provider_view, providers, shares

router = APIRouter(prefix="/api", tags=["shares"])


def _existing_matter(matter_id: int, session: SessionDep) -> int:
    if not matter_queries.matter_exists(session, matter_id):
        raise HTTPException(status_code=404, detail=f"Matter {matter_id} not found")
    return matter_id


def _existing_share(share_id: int, session: SessionDep) -> Share:
    try:
        return shares.get_share(session, share_id)
    except shares.ShareNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


def _current_user(session: SessionDep, x_user_id: Annotated[int, Header()]) -> User:
    # Stub accounts, chosen by the header the firm view's user switcher sets.
    try:
        return shares.require_user(session, x_user_id)
    except shares.UnknownUser as error:
        raise HTTPException(status_code=401, detail=str(error)) from error


MatterId = Annotated[int, Depends(_existing_matter)]
ExistingShare = Annotated[Share, Depends(_existing_share)]
CurrentUser = Annotated[User, Depends(_current_user)]


def _one(session: SessionDep, share: Share) -> ShareOut:
    return shares.shares_out(session, [share])[0]


@router.get("/matters/{matter_id}/providers")
def list_providers(matter_id: MatterId, session: SessionDep) -> list[ProviderOut]:
    return providers.providers_panel(session, matter_id, datetime.now(UTC))


@router.get("/matters/{matter_id}/shares")
def list_shares(matter_id: MatterId, session: SessionDep) -> list[ShareOut]:
    return shares.shares_out(session, shares.list_shares(session, matter_id))


@router.post("/matters/{matter_id}/shares", status_code=201)
def create_share(
    matter_id: MatterId, body: ShareCreate, user: CurrentUser, session: SessionDep
) -> ShareOut:
    try:
        share = shares.create_share(session, matter_id, body, user, datetime.now(UTC))
    except shares.NotAProvider as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _one(session, share)


@router.get("/shares/{share_id}/preview")
def preview_share(share: ExistingShare, session: SessionDep) -> SharePreviewOut:
    try:
        return provider_view.share_preview(session, share, datetime.now(UTC))
    except provider_view.ShareGone as error:
        raise HTTPException(status_code=410, detail=str(error)) from error


@router.patch("/shares/{share_id}")
def update_share(
    share: ExistingShare, body: ShareUpdate, session: SessionDep
) -> ShareOut:
    try:
        shares.update_share(session, share, body)
    except shares.ShareRevoked as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except shares.InvalidShareUpdate as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _one(session, share)


@router.post("/shares/{share_id}/revoke")
def revoke_share(share: ExistingShare, session: SessionDep) -> ShareOut:
    shares.revoke_share(session, share, datetime.now(UTC))
    return _one(session, share)
