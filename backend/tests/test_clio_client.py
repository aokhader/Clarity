from pathlib import Path

import httpx
import pytest

from app.clio.client import ClioClient, ClioError, ClioWriteForbidden


def _client(handler, sleeps: list[float] | None = None) -> ClioClient:
    return ClioClient(
        get_token=lambda: "token",
        transport=httpx.MockTransport(handler),
        sleep=(sleeps.append if sleeps is not None else lambda _s: None),
    )


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_any_non_get_request_is_refused(data_dir: Path, method: str) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={})

    client = _client(handler)
    with pytest.raises(ClioWriteForbidden):
        client.request(method, "notes.json")
    # Also through the underlying transport, in case anything bypasses `request`.
    with pytest.raises(ClioWriteForbidden):
        client._http.request(method, "notes.json")
    assert sent == []


def test_paging_follows_next_until_absent(data_dir: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params.get("page", "1"))
        meta = {"paging": {}}
        if page < 3:
            meta["paging"]["next"] = (
                f"https://app.clio.com/api/v4/notes.json?page={page + 1}"
            )
        return httpx.Response(200, json={"data": [{"id": page}], "meta": meta})

    records = _client(handler).get_all("notes.json", {"fields": "id"})
    assert [r["id"] for r in records] == [1, 2, 3]


def test_rate_limit_waits_for_retry_after_and_retries(data_dir: Path) -> None:
    calls = {"count": 0}
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(429, headers={"Retry-After": "7"})
        return httpx.Response(200, json={"data": {"id": 1}})

    result = _client(handler, sleeps).get("matters/1.json", {"fields": "id"})
    assert result["data"]["id"] == 1
    assert sleeps == [7.0]
    assert calls["count"] == 2


def test_failed_signed_download_raises_clio_error_without_signature(
    data_dir: Path,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "app.clio.com":
            return httpx.Response(
                303, headers={"Location": "https://files.example/doc?sig=secret"}
            )
        return httpx.Response(403, text="expired")

    with pytest.raises(ClioError) as caught:
        _client(handler).download("documents/1/download.json", data_dir / "1.pdf")
    assert caught.value.status == 403
    assert "secret" not in str(caught.value)


def test_dropped_connection_is_retried(data_dir: Path) -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.ReadTimeout("timed out", request=request)
        return httpx.Response(200, json={"data": {"id": 1}})

    assert _client(handler).get("matters/1.json", {"fields": "id"})["data"]["id"] == 1
    assert calls["count"] == 2
