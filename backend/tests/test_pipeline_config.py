"""Retry counts, timeouts and batch sizes come from `config.py`, so `.env` can tune them."""

from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from app.clio.client import ClioClient, ClioError
from app.config import Settings, get_settings
from app.digest import llm


def test_the_clio_retry_count_comes_from_config(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLIO_MAX_ATTEMPTS", "2")
    get_settings.cache_clear()
    sent: list[httpx.Request] = []

    def unavailable(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(503, json={})

    client = ClioClient(
        get_token=lambda: "token",
        transport=httpx.MockTransport(unavailable),
        sleep=lambda _s: None,
    )
    with pytest.raises(ClioError):
        client.get("notes.json")
    assert len(sent) == 2


def test_the_model_retry_count_comes_from_config(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_MAX_ATTEMPTS", "3")
    get_settings.cache_clear()
    posts: list[str] = []

    def overloaded(url: str, **_kwargs: object) -> httpx.Response:
        posts.append(url)
        return httpx.Response(529, json={})

    monkeypatch.setattr(llm.httpx, "post", overloaded)
    monkeypatch.setattr(llm.time, "sleep", lambda _s: None)

    response = llm._post("https://model.invalid/messages")

    assert response.status_code == 529
    assert len(posts) == 3


def test_a_clio_page_larger_than_clio_allows_is_refused() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, clio_page_limit=500)  # type: ignore[call-arg]
