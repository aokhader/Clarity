"""Sync and digest status: a job that fails before it records a run still reports why.

Without this, a sync stopped by a missing Clio token or an unmatched matter left only a
log line, and the status kept showing the previous run as if nothing had been tried.
"""

import threading
import time
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_sessionmaker
from app.models import SyncRun
from app.services import jobs

IDLE_TIMEOUT_S = 10.0


@pytest.fixture(autouse=True)
def no_start_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test starts with no start failure left over from another."""
    monkeypatch.setattr(jobs, "_start_failures", {})


def _wait_until_idle(client: TestClient, job: str) -> dict[str, Any]:
    deadline = time.monotonic() + IDLE_TIMEOUT_S
    while time.monotonic() < deadline:
        status = client.get(f"/api/ops/{job}/status").json()
        if not status["running"]:
            return status
        time.sleep(0.05)
    raise AssertionError(f"The {job} job was still running after {IDLE_TIMEOUT_S}s")


def _failing(message: str) -> Callable[[Session], None]:
    def work(session: Session) -> None:
        raise RuntimeError(message)

    return work


def test_a_sync_with_no_clio_token_reports_why_it_did_not_start(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A query is set, so the sync gets as far as asking for a token, and none is stored.
    monkeypatch.setenv("CLIO_MATTER_QUERY", "any matter")
    get_settings.cache_clear()

    assert client.post("/api/ops/sync").status_code == 202
    status = _wait_until_idle(client, "sync")

    assert status["last_run"] is None
    assert status["start_failure"] is not None
    assert status["start_failure"]["error"]
    assert status["start_failure"]["at"]


def test_a_start_failure_leaves_the_previous_run_as_the_last_run(
    client: TestClient, seeded: Session
) -> None:
    before = client.get("/api/ops/sync/status").json()
    assert before["last_run"] is not None
    assert before["start_failure"] is None

    jobs.start_job(jobs.Job.SYNC, _failing("could not start"))
    status = _wait_until_idle(client, "sync")

    assert status["last_run"] == before["last_run"]
    assert status["start_failure"]["error"] == "could not start"


def test_a_later_run_clears_the_start_failure(client: TestClient) -> None:
    jobs.start_job(jobs.Job.SYNC, _failing("could not start"))
    assert _wait_until_idle(client, "sync")["start_failure"] is not None

    with get_sessionmaker()() as session:
        session.add(SyncRun(matter_id=1))
        session.commit()

    status = client.get("/api/ops/sync/status").json()
    assert status["start_failure"] is None
    assert status["last_run"] is not None


def test_a_failure_after_the_run_row_exists_is_left_to_that_row(
    client: TestClient,
) -> None:
    def fails_mid_run(session: Session) -> None:
        session.add(SyncRun(matter_id=1))
        session.commit()
        raise RuntimeError("stopped mid-run")

    jobs.start_job(jobs.Job.SYNC, fails_mid_run)
    status = _wait_until_idle(client, "sync")

    assert status["start_failure"] is None
    assert status["last_run"] is not None


def test_a_digest_start_failure_shows_on_the_digest_status_only(
    client: TestClient,
) -> None:
    jobs.start_job(jobs.Job.DIGEST, _failing("nothing to digest"))

    assert _wait_until_idle(client, "digest")["start_failure"]["error"] == (
        "nothing to digest"
    )
    assert client.get("/api/ops/sync/status").json()["start_failure"] is None


def test_a_second_job_is_refused_while_one_runs(client: TestClient) -> None:
    release = threading.Event()

    def waits(session: Session) -> None:
        release.wait(IDLE_TIMEOUT_S)

    jobs.start_job(jobs.Job.DIGEST, waits)
    try:
        assert client.post("/api/ops/sync").status_code == 409
    finally:
        release.set()
    _wait_until_idle(client, "digest")
