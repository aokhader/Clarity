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
from app.models import LlmCall, SyncRun
from app.services import jobs
from tests.fixtures.synthetic_matter import MATTER_ID

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


# --- D29: retry the model calls that failed ---------------------------------------------


@pytest.fixture
def digest_runs(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Stand in for pipeline's run_digest, so no model is called; record each call."""
    import app.digest.run as digest_run

    calls: list[dict[str, Any]] = []

    def run_digest(
        session: Session, matter_id: int, retry_failed: bool = False
    ) -> None:
        calls.append({"matter_id": matter_id, "retry_failed": retry_failed})

    monkeypatch.setattr(digest_run, "run_digest", run_digest)
    return calls


def test_a_digest_retries_failed_calls_only_when_asked(
    client: TestClient, seeded: Session, digest_runs: list[dict[str, Any]]
) -> None:
    assert client.post("/api/ops/digest").status_code == 202
    _wait_until_idle(client, "digest")
    response = client.post("/api/ops/digest", json={"retry_failed": True})
    assert response.status_code == 202, response.text
    _wait_until_idle(client, "digest")

    assert digest_runs == [
        {"matter_id": MATTER_ID, "retry_failed": False},
        {"matter_id": MATTER_ID, "retry_failed": True},
    ]


def _call(key: str, *, error: str | None = None, hit: bool = False) -> LlmCall:
    return LlmCall(
        matter_id=MATTER_ID,
        purpose="extract_page",
        model="test-model",
        cache_key=key,
        response_json=None if error or hit else {"facts": []},
        cache_hit=hit,
        error=error,
    )


def test_the_digest_status_counts_calls_cached_as_failed(
    client: TestClient, seeded: Session
) -> None:
    seeded.add_all(
        [
            _call("failed", error="HTTP 500"),
            # A failure answered again from the cache is the same failed call.
            _call("failed", error="earlier call failed: HTTP 500", hit=True),
            _call("failed twice", error="timeout"),
            _call("failed twice", error="timeout"),
            # A call that failed and then succeeded is answered by the success.
            _call("recovered", error="timeout"),
            _call("recovered"),
            _call("succeeded"),
        ]
    )
    seeded.commit()

    status = client.get("/api/ops/digest/status").json()

    assert status["cached_failed_calls"] == 2
    assert client.get("/api/ops/sync/status").json()["cached_failed_calls"] is None


def test_no_failed_calls_means_nothing_to_retry(
    client: TestClient, seeded: Session
) -> None:
    assert client.get("/api/ops/digest/status").json()["cached_failed_calls"] == 0
