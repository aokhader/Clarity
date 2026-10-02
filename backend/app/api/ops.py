"""Operational routes: health now; sync, digest, and cost triggers in later milestones."""

from fastapi import APIRouter

from app.config import get_settings
from app.db import SessionDep, check_database
from app.schemas import HealthOut

router = APIRouter(prefix="/api/ops", tags=["ops"])


@router.get("/health")
def health(session: SessionDep) -> HealthOut:
    check_database(session)
    settings = get_settings()
    return HealthOut(
        status="ok",
        clio_configured=settings.clio_configured,
        models_configured=settings.models_configured,
    )
