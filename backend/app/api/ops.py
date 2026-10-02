"""Operational routes: health, sync and digest triggers with status, and the cost figure.

Sync and digest run in a background thread with their own session, never inside a
request, so no page load waits on Clio or a model.
"""

import logging
import threading
from collections.abc import Callable

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionDep, check_database, get_sessionmaker
from app.models import DigestRun, LlmCall, Page, Source, SyncRun
from app.schemas import CostOut, HealthOut, RunOut, RunStatusOut

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ops", tags=["ops"])

_job_lock = threading.Lock()


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
    _start(_run_sync)
    return sync_status(session)


@router.get("/sync/status")
def sync_status(session: SessionDep) -> RunStatusOut:
    return _status(session.scalars(select(SyncRun).order_by(SyncRun.id.desc())).first())


@router.post("/digest", status_code=202)
def start_digest(session: SessionDep) -> RunStatusOut:
    _start(_run_digest)
    return digest_status(session)


@router.get("/digest/status")
def digest_status(session: SessionDep) -> RunStatusOut:
    return _status(
        session.scalars(select(DigestRun).order_by(DigestRun.id.desc())).first()
    )


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


def _status(run: SyncRun | DigestRun | None) -> RunStatusOut:
    last = None
    if run is not None:
        last = RunOut(
            id=run.id,
            started_at=run.started_at,
            finished_at=run.finished_at,
            error=run.error,
            stats=run.stats_json,
        )
    return RunStatusOut(running=_job_lock.locked(), last_run=last)


def _start(job: Callable[[Session], None]) -> None:
    if not _job_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=409, detail="A sync or digest is already running"
        )

    def target() -> None:
        try:
            with get_sessionmaker()() as session:
                job(session)
        except Exception:
            log.exception("Background job failed")
        finally:
            _job_lock.release()

    threading.Thread(target=target, daemon=True).start()


def _run_sync(session: Session) -> None:
    from app.clio.client import ClioClient
    from app.clio.oauth import TokenStore
    from app.clio.sync import resolve_matter_id, sync_matter

    tokens = TokenStore(session)
    client = ClioClient(tokens.access_token, tokens.refresh)
    try:
        matter_id = resolve_matter_id(client, get_settings().clio_matter_query, None)
        sync_matter(session, client, matter_id)
    finally:
        client.close()


def _run_digest(session: Session) -> None:
    from app.digest.run import run_digest, synced_matter_id

    run_digest(session, synced_matter_id(session))
