"""Provider routes under `/api/p/{token}`. The token is the credential. Owned by Track C.

Every response is built in `services/provider_view.py` from `visible_facts_for_share`.
An unknown token is 404; an expired or revoked one is 410, so the page can say which.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse

from app.db import SessionDep
from app.schemas import ProviderPayload, ProviderSourceOut
from app.services import provider_sources, provider_view, shares, source_views

router = APIRouter(prefix="/api/p", tags=["provider"])

# The link is the credential: keep responses out of shared caches and history.
_NO_STORE = {"Cache-Control": "no-store"}


def _http_error(error: Exception) -> HTTPException:
    match error:
        case provider_view.ShareGone():
            return HTTPException(410, "This link has expired or was withdrawn.")
        case _:
            return HTTPException(404, "Not found.")


@router.get("/{token}")
def provider_page(
    token: str, session: SessionDep, response: Response
) -> ProviderPayload:
    response.headers.update(_NO_STORE)
    try:
        return provider_view.open_link(session, token, datetime.now(UTC))
    except (shares.ShareNotFound, provider_view.ShareGone) as error:
        raise _http_error(error) from error


@router.get("/{token}/facts/{fact_id}/source")
def provider_source(
    token: str, fact_id: int, session: SessionDep, response: Response
) -> ProviderSourceOut:
    response.headers.update(_NO_STORE)
    try:
        return provider_sources.provider_source(
            session, token, fact_id, datetime.now(UTC)
        )
    except (
        shares.ShareNotFound,
        provider_view.ShareGone,
        provider_sources.NotVisible,
    ) as error:
        raise _http_error(error) from error


@router.get("/{token}/pages/{page_id}/image", response_class=FileResponse)
def provider_page_image(token: str, page_id: int, session: SessionDep) -> FileResponse:
    try:
        path = provider_sources.provider_page_image(
            session, token, page_id, datetime.now(UTC)
        )
    except (
        shares.ShareNotFound,
        provider_view.ShareGone,
        provider_sources.NotVisible,
        source_views.PageNotFound,
    ) as error:
        raise _http_error(error) from error
    return FileResponse(path, media_type="image/png", headers=_NO_STORE)
