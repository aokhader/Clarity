"""Background sync and digest jobs: one at a time, off the request path, with their status.

A job records its own run row (`sync_runs`, `digest_runs`), and the status reports the
latest one. A job that fails before it writes that row (no Clio token, no matching
matter, nothing synced yet) would leave only a log line, and the status would keep
showing the previous run as if the new attempt had never happened. Such a failure is
kept here, in process memory beside the lock that says whether a job is running, and
reported until a newer run row supersedes it.
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_sessionmaker
from app.models import DigestRun, LlmCall, SyncRun
from app.schemas import RunOut, RunStatusOut, StartFailureOut
from app.services.cost import CHAT_PURPOSE

log = logging.getLogger(__name__)

# Same bound as the run rows' `error` column.
MAX_ERROR_CHARS = 2000

JobWork = Callable[[Session], None]


class Job(StrEnum):
    SYNC = "sync"
    DIGEST = "digest"


RUN_MODEL: dict[Job, type[SyncRun] | type[DigestRun]] = {
    Job.SYNC: SyncRun,
    Job.DIGEST: DigestRun,
}


class JobAlreadyRunning(Exception):
    """A sync or digest is running; they share one lock so they never overlap."""


@dataclass(frozen=True)
class _StartFailure:
    run_id_before: int | None
    at: datetime
    error: str


_lock = threading.Lock()
_start_failures: dict[Job, _StartFailure] = {}


def start_job(job: Job, work: JobWork) -> None:
    """Run `work` in a background thread with its own session, or refuse if one runs."""
    if not _lock.acquire(blocking=False):
        raise JobAlreadyRunning("A sync or digest is already running")

    def target() -> None:
        try:
            _run(job, work)
        except Exception:
            log.exception("The %s job could not open a session", job)
        finally:
            _lock.release()

    threading.Thread(target=target, daemon=True).start()


def job_status(session: Session, job: Job) -> RunStatusOut:
    model = RUN_MODEL[job]
    run = session.scalars(select(model).order_by(model.id.desc())).first()
    last_run = None
    if run is not None:
        last_run = RunOut(
            id=run.id,
            started_at=run.started_at,
            finished_at=run.finished_at,
            error=run.error,
            stats=run.stats_json,
        )
    failure = _start_failures.get(job)
    start_failure = None
    if failure is not None and failure.run_id_before == (run.id if run else None):
        start_failure = StartFailureOut(at=failure.at, error=failure.error)
    return RunStatusOut(
        running=_lock.locked(),
        last_run=last_run,
        start_failure=start_failure,
        cached_failed_calls=cached_failed_calls(session) if job is Job.DIGEST else None,
    )


def cached_failed_calls(session: Session) -> int:
    """Requests a digest would answer from the cache as failed (D29).

    The rule of `digest/llm.py:_lookup`: a request whose call failed, and that has no
    successful response, is not sent again unless the digest retries failed calls. A
    chat answer (D49) is never part of a digest, so its failures are not counted.
    """
    # A failed call stores JSON null, which SQL does not count as NULL.
    succeeded = select(LlmCall.cache_key).where(
        func.coalesce(func.json_type(LlmCall.response_json), "null") != "null"
    )
    return (
        session.scalar(
            select(func.count(distinct(LlmCall.cache_key))).where(
                LlmCall.cache_hit.is_(False),
                LlmCall.error.is_not(None),
                LlmCall.purpose != CHAT_PURPOSE,
                LlmCall.cache_key.not_in(succeeded),
            )
        )
        or 0
    )


def sync_configured_matter(session: Session) -> None:
    """Find the matter named in `.env` and sync it from Clio."""
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


def digest_synced_matter(session: Session, *, retry_failed: bool = False) -> None:
    """Digest the synced matter, as `cli digest` does, with its --retry-failed."""
    from app.digest.run import run_digest, synced_matter_id

    run_digest(session, synced_matter_id(session), retry_failed=retry_failed)


def _run(job: Job, work: JobWork) -> None:
    with get_sessionmaker()() as session:
        run_id_before = _latest_run_id(session, job)
        try:
            work(session)
        except Exception as error:
            log.exception("The %s job failed", job)
            session.rollback()
            # A failure after the run row exists is that row's to report.
            if _latest_run_id(session, job) == run_id_before:
                _start_failures[job] = _StartFailure(
                    run_id_before=run_id_before,
                    at=datetime.now(UTC),
                    error=(str(error) or type(error).__name__)[:MAX_ERROR_CHARS],
                )


def _latest_run_id(session: Session, job: Job) -> int | None:
    return session.scalar(select(func.max(RUN_MODEL[job].id)))
