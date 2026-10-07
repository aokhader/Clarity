"""Operational routes: health, sync and digest triggers with status, and the cost figure.

Sync and digest run in a background thread with their own session (`services/jobs.py`),
never inside a request, so no page load waits on Clio or a model.
"""

from functools import partial

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from app.config import get_settings
from app.db import SessionDep, check_database
from app.models import LlmCall, Page, Source
from app.schemas import CostOut, DigestStartIn, HealthOut, RunStatusOut
from app.services.jobs import (
    Job,
    JobAlreadyRunning,
    JobWork,
    digest_synced_matter,
    job_status,
    start_job,
    sync_configured_matter,
)

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


@router.post("/sync", status_code=202)
def start_sync(session: SessionDep) -> RunStatusOut:
    _start(Job.SYNC, sync_configured_matter)
    return job_status(session, Job.SYNC)


@router.get("/sync/status")
def sync_status(session: SessionDep) -> RunStatusOut:
    return job_status(session, Job.SYNC)


@router.post("/digest", status_code=202)
def start_digest(
    session: SessionDep, body: DigestStartIn | None = None
) -> RunStatusOut:
    retry_failed = body.retry_failed if body else False
    _start(Job.DIGEST, partial(digest_synced_matter, retry_failed=retry_failed))
    return job_status(session, Job.DIGEST)


@router.get("/digest/status")
def digest_status(session: SessionDep) -> RunStatusOut:
    return job_status(session, Job.DIGEST)


@router.get("/cost")
def cost(session: SessionDep, matter_id: int | None = None) -> CostOut:
    """Tokens and dollars actually paid. Cache hits cost nothing and are counted apart."""
    if matter_id is None:
        matter_id = session.scalar(select(Source.matter_id).order_by(Source.id))
    if matter_id is None:
        raise HTTPException(status_code=404, detail="Nothing synced yet")
    calls, hits, tokens_in, tokens_out, micro = session.execute(
        select(
            func.count(LlmCall.id).filter(LlmCall.cache_hit.is_(False)),
            func.count(LlmCall.id).filter(LlmCall.cache_hit.is_(True)),
            func.coalesce(func.sum(LlmCall.input_tokens), 0),
            func.coalesce(func.sum(LlmCall.output_tokens), 0),
            func.coalesce(func.sum(LlmCall.cost_micro_usd), 0),
        ).where(LlmCall.matter_id == matter_id)
    ).one()
    pages = session.scalar(
        select(func.count(Page.id)).join(Source).where(Source.matter_id == matter_id)
    )
    return CostOut(
        matter_id=matter_id,
        pages=pages or 0,
        model_calls=calls,
        cache_hits=hits,
        input_tokens=tokens_in,
        output_tokens=tokens_out,
        cost_micro_usd=micro,
    )


def _start(job: Job, work: JobWork) -> None:
    try:
        start_job(job, work)
    except JobAlreadyRunning as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
