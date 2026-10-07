"""Every sync run is closed, however it stops.

A run row with no `finished_at` and no `error` reads as a sync still in progress, and
it hides why the last sync failed. Clio's own errors were recorded; anything else (an
auth failure mid-run, an interrupt) left the row open.
"""

from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clio.client import ClioClient
from app.clio.oauth import ClioNotAuthorized
from app.clio.sync import sync_matter
from app.models import SyncRun

MATTER = 1


def _client(
    handler: Callable[[httpx.Request], httpx.Response],
    refresh: Callable[[], str] | None = None,
) -> ClioClient:
    return ClioClient(
        get_token=lambda: "token",
        refresh_token=refresh,
        transport=httpx.MockTransport(handler),
        sleep=lambda _s: None,
    )


def _only_run(session: Session) -> SyncRun:
    session.expire_all()
    return session.scalars(select(SyncRun)).one()


def test_an_auth_failure_mid_sync_closes_the_run_and_is_raised(
    data_dir: Path, session: Session
) -> None:
    def refresh() -> str:
        raise ClioNotAuthorized("Token request failed (400)")

    client = _client(lambda _r: httpx.Response(401, json={}), refresh)
    with pytest.raises(ClioNotAuthorized):
        sync_matter(session, client, MATTER)

    run = _only_run(session)
    assert run.finished_at is not None
    assert run.error is not None and "Token request failed" in run.error
    assert run.stats_json is not None and run.stats_json["errors"]


def test_an_interrupted_sync_closes_the_run_and_is_raised(
    data_dir: Path, session: Session
) -> None:
    def interrupt(_request: httpx.Request) -> httpx.Response:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        sync_matter(session, _client(interrupt), MATTER)

    run = _only_run(session)
    assert run.finished_at is not None
    assert run.error == "KeyboardInterrupt"


def test_a_clio_refusal_still_closes_the_run_and_returns_it(
    data_dir: Path, session: Session
) -> None:
    run = sync_matter(session, _client(lambda _r: httpx.Response(403, json={})), MATTER)

    assert run.finished_at is not None
    assert run.error is not None and "403" in run.error
    assert _only_run(session).id == run.id
