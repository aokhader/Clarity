"""Every sync run is closed, however it stops, and a sync that missed items is redone.

A run row with no `finished_at` and no `error` reads as a sync still in progress, and
it hides why the last sync failed. Clio's own errors were recorded; anything else (an
auth failure mid-run, an interrupt) left the row open.

A run whose items partly failed still counted as the clean baseline for the next run's
`updated_since`, and a document's new ETag was saved before its file came down, so
what one sync missed was never pulled again.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clio.client import ClioClient
from app.clio.oauth import ClioNotAuthorized
from app.clio.sync import sync_matter
from app.models import Source, SourceType, SyncRun

MATTER = 1
FILE_HOST = "files.invalid"


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


class FakeClio:
    """Answers every request a sync makes; serves one list of documents and their file."""

    def __init__(self) -> None:
        self.documents: list[dict[str, Any]] = []
        self.file_status = 200
        self.file_bytes = b""
        self.list_params: dict[str, httpx.QueryParams] = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == FILE_HOST:
            return httpx.Response(self.file_status, content=self.file_bytes)
        path = request.url.path.split("/api/v4/", 1)[-1]
        if path.endswith("/download.json"):
            location = f"https://{FILE_HOST}/{path}?signature=x"
            return httpx.Response(303, headers={"Location": location})
        if path == f"matters/{MATTER}.json":
            return httpx.Response(200, json={"data": {"id": MATTER, "etag": "m"}})
        self.list_params[path] = request.url.params
        data = self.documents if path == "documents.json" else []
        return httpx.Response(200, json={"data": data, "meta": {"paging": {}}})


def _past_run(session: Session, started: datetime, errors: list[str]) -> None:
    session.add(
        SyncRun(
            matter_id=MATTER,
            started_at=started,
            finished_at=started + timedelta(minutes=1),
            stats_json={"counts": {}, "errors": errors},
        )
    )
    session.commit()


def test_a_sync_that_missed_items_is_not_the_baseline_for_the_next(
    data_dir: Path, session: Session
) -> None:
    clean = datetime(2020, 1, 1, tzinfo=UTC)
    _past_run(session, clean, [])
    _past_run(session, clean + timedelta(days=1), ["note: not available (403)"])

    clio = FakeClio()
    sync_matter(session, _client(clio), MATTER)

    since = clio.list_params["notes.json"]["updated_since"]
    assert since.startswith("2020-01-01T00:00:00")


def test_a_failed_download_of_an_updated_document_is_retried_next_sync(
    data_dir: Path, session: Session
) -> None:
    clio = FakeClio()
    clio.documents = [{"id": 5, "etag": "v1", "filename": "scan.pdf"}]
    clio.file_bytes = b"first version"
    sync_matter(session, _client(clio), MATTER)

    clio.documents = [{"id": 5, "etag": "v2", "filename": "scan.pdf"}]
    clio.file_status = 500
    failed = sync_matter(session, _client(clio), MATTER)
    assert failed.stats_json is not None and failed.stats_json["errors"]

    clio.file_status = 200
    clio.file_bytes = b"second version"
    sync_matter(session, _client(clio), MATTER)

    assert (data_dir / "files" / "5.pdf").read_bytes() == b"second version"
    session.expire_all()
    document = session.scalars(
        select(Source).where(Source.clio_type == SourceType.DOCUMENT)
    ).one()
    assert document.etag == "v2"
