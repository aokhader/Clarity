"""Firm-view routes for a fact's source and rendered page images. Owned by Track B."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.db import SessionDep
from app.schemas import FactSourceOut
from app.services import source_views

router = APIRouter(prefix="/api", tags=["facts"])


@router.get("/facts/{fact_id}/source")
def fact_source(fact_id: int, session: SessionDep) -> FactSourceOut:
    try:
        return source_views.fact_source(session, fact_id)
    except source_views.FactNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/pages/{page_id}/image", response_class=FileResponse)
def page_image(page_id: int, session: SessionDep) -> FileResponse:
    try:
        path = source_views.page_image_path(session, page_id)
    except source_views.PageNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return FileResponse(path, media_type="image/png")
