"""GET-only Clio API client.

Clio is input only: the competition disqualifies builds that write case data. The
transport refuses every verb except GET, so no code path here can create, update, or
delete anything in Clio, and `tests/test_clio_client.py` proves it.
"""

import logging
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 6
# Clio caps list pages at 200 records.
PAGE_LIMIT = 200


class ClioError(Exception):
    """A Clio request failed after retries."""

    def __init__(self, status: int, url: str, body: str) -> None:
        super().__init__(f"Clio {status} on {url}: {body[:300]}")
        self.status = status
        self.url = url
        self.body = body


class ClioWriteForbidden(Exception):
    """Raised when anything tries to send a non-GET request to Clio."""


class ClioRateLimited(ClioError):
    """Clio kept answering 429 after every retry."""


class _GetOnlyTransport(httpx.BaseTransport):
    """Wraps the real transport and rejects any request that is not a GET."""

    def __init__(self, inner: httpx.BaseTransport) -> None:
        self._inner = inner

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if request.method != "GET":
            raise ClioWriteForbidden(f"Blocked {request.method} {request.url}")
        return self._inner.handle_request(request)

    def close(self) -> None:
        self._inner.close()


TokenGetter = Callable[[], str]
TokenRefresher = Callable[[], str]


class ClioClient:
    def __init__(
        self,
        get_token: TokenGetter,
        refresh_token: TokenRefresher | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        settings = get_settings()
        self._get_token = get_token
        self._refresh_token = refresh_token
        self._sleep = sleep
        self.request_count = 0
        inner = transport or httpx.HTTPTransport(retries=2)
        self._http = httpx.Client(
            base_url=settings.clio_api_url,
            transport=_GetOnlyTransport(inner),
            headers={"X-API-VERSION": settings.clio_api_version},
            timeout=60,
            follow_redirects=False,
        )
        # Signed download URLs must not receive the Clio bearer token, so they go
        # through a separate client with no default headers. Still GET-only.
        self._files = httpx.Client(
            transport=_GetOnlyTransport(transport or httpx.HTTPTransport(retries=2)),
            timeout=120,
            follow_redirects=True,
        )

    def close(self) -> None:
        self._http.close()
        self._files.close()

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """The only way out. Anything but GET is refused before it is built."""
        if method.upper() != "GET":
            raise ClioWriteForbidden(f"Blocked {method} {url}")
        return self._send(url, kwargs.get("params"))

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self._send(path, params)
        return response.json()

    def get_all(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Follow `meta.paging.next` until it is absent and return every record."""
        return list(self.iter_all(path, params))

    def iter_all(self, path: str, params: dict[str, Any]) -> Iterator[dict[str, Any]]:
        payload = self.get(path, {"limit": PAGE_LIMIT, **params})
        while True:
            data = payload.get("data") or []
            yield from data if isinstance(data, list) else [data]
            next_url = ((payload.get("meta") or {}).get("paging") or {}).get("next")
            if not next_url:
                return
            # `next` is absolute and already carries the query string.
            payload = self._send(next_url, None).json()

    def download(self, path: str, destination: Path) -> int:
        """Fetch a document. Clio answers with a 303 to a signed URL on another host."""
        response = self._send(path, None, allow_redirect=True)
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers["Location"]
            file_response = self._files.get(location)
            file_response.raise_for_status()
            content = file_response.content
        else:
            content = response.content
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return len(content)

    def _send(
        self, url: str, params: dict[str, Any] | None, allow_redirect: bool = False
    ) -> httpx.Response:
        refreshed = False
        response: httpx.Response | None = None
        for attempt in range(MAX_ATTEMPTS):
            headers = {"Authorization": f"Bearer {self._get_token()}"}
            response = self._http.get(url, params=params, headers=headers)
            self.request_count += 1
            status = response.status_code
            if status == 429:
                wait = _retry_after(response, attempt)
                log.info("Clio rate limit hit; waiting %.0fs", wait)
                self._sleep(wait)
                continue
            if status == 401 and self._refresh_token and not refreshed:
                self._refresh_token()
                refreshed = True
                continue
            if status >= 500:
                self._sleep(min(2**attempt, 30))
                continue
            if allow_redirect and status in (301, 302, 303, 307, 308):
                return response
            if status >= 400:
                raise ClioError(status, str(response.url), response.text)
            self._respect_budget(response)
            return response
        assert response is not None
        if response.status_code == 429:
            raise ClioRateLimited(429, str(response.url), response.text)
        raise ClioError(response.status_code, str(response.url), response.text)

    def _respect_budget(self, response: httpx.Response) -> None:
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining is None or not remaining.strip().isdigit() or int(remaining) > 0:
            return
        wait = _seconds_until_reset(response.headers.get("X-RateLimit-Reset"))
        log.info("Clio request budget spent; waiting %.0fs for reset", wait)
        self._sleep(wait)


def _retry_after(response: httpx.Response, attempt: int) -> float:
    value = response.headers.get("Retry-After", "")
    try:
        return max(float(value), 1.0)
    except ValueError:
        return float(min(2**attempt, 60))


def _seconds_until_reset(value: str | None) -> float:
    """X-RateLimit-Reset may be an epoch timestamp or a number of seconds."""
    try:
        number = float(value or "")
    except ValueError:
        return 60.0
    if number > 1_000_000_000:
        return max(number - time.time(), 1.0)
    return max(number, 1.0)
