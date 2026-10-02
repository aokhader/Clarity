"""Read-only Clio API client.

Read-only by construction: the HTTP session refuses any method other than GET,
so no code path in this project can create, update or delete Clio data.
"""
import time

import requests

from . import config
from .auth import TokenProvider


class ClioHTTPError(Exception):
    def __init__(self, status: int, url: str, body: str):
        super().__init__(f"Clio {status} on {url}: {body[:300]}")
        self.status = status
        self.url = url
        self.body = body


class _GetOnlySession(requests.Session):
    def request(self, method, url, *args, **kwargs):
        if method.upper() != "GET":
            raise PermissionError(f"Blocked {method} {url}: this client is read-only.")
        return super().request(method, url, *args, **kwargs)


class ClioReadOnlyClient:
    def __init__(self, base_url: str = config.CLIO_API_URL, tokens: TokenProvider | None = None,
                 max_retries: int = 6, verbose: bool = True):
        self.base_url = base_url.rstrip("/")
        self.tokens = tokens or TokenProvider()
        self.session = _GetOnlySession()
        self.max_retries = max_retries
        self.verbose = verbose
        self.request_count = 0

    def _url(self, path_or_url: str) -> str:
        if path_or_url.startswith("http"):
            return path_or_url
        return f"{self.base_url}/{path_or_url.lstrip('/')}"

    def _get(self, path_or_url: str, params: dict | None = None, stream: bool = False) -> requests.Response:
        url = self._url(path_or_url)
        refreshed = False
        for attempt in range(self.max_retries):
            headers = {"Authorization": f"Bearer {self.tokens.get()}", "Accept": "application/json"}
            resp = self.session.get(url, params=params, headers=headers, timeout=60, stream=stream)
            self.request_count += 1

            if resp.status_code == 429:
                wait = float(resp.headers.get("Retry-After") or 2 ** attempt)
                if self.verbose:
                    print(f"  rate limited, waiting {wait:.0f}s")
                time.sleep(wait)
                continue
            if resp.status_code == 401 and not refreshed and self.tokens.can_refresh():
                self.tokens.refresh()
                refreshed = True
                continue
            if resp.status_code >= 500:
                time.sleep(min(2 ** attempt, 20))
                continue
            if resp.status_code >= 400:
                raise ClioHTTPError(resp.status_code, resp.url, resp.text)

            # Be polite when the budget is nearly spent
            remaining = resp.headers.get("X-RateLimit-Remaining")
            if remaining is not None and remaining.isdigit() and int(remaining) <= 1:
                time.sleep(float(resp.headers.get("X-RateLimit-Reset-After", 5) or 5))
            return resp
        raise ClioHTTPError(resp.status_code, resp.url, resp.text)

    def get(self, path: str, params: dict | None = None) -> dict:
        """Single request, returns parsed JSON."""
        return self._get(path, params).json()

    def get_all(self, path: str, params: dict | None = None) -> list[dict]:
        """Follow meta.paging.next until exhausted and return every record."""
        params = {"limit": config.PAGE_LIMIT, **(params or {})}
        records: list[dict] = []
        payload = self.get(path, params)
        while True:
            data = payload.get("data", [])
            records.extend(data if isinstance(data, list) else [data])
            next_url = (payload.get("meta") or {}).get("paging", {}).get("next")
            if not next_url:
                return records
            payload = self.get(next_url)  # next_url already carries the query string

    def download(self, path: str, dest) -> int:
        """Stream a file (e.g. documents/{id}/download) to disk; returns bytes written."""
        resp = self._get(path, stream=True)
        size = 0
        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 16):
                fh.write(chunk)
                size += len(chunk)
        return size
