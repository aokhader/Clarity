"""No more model requests per minute than config allows, per model (D31).

Every HTTP attempt counts, the first try and each retry alike. A fake clock stands in
for time, so the tests never wait.
"""

import httpx
import pytest
from pydantic import BaseModel

from app.config import Settings
from app.digest import llm


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    fake = FakeClock()
    monkeypatch.setattr(llm, "_LIMITER", llm.RateLimiter(clock=fake, sleep=fake.sleep))
    monkeypatch.setattr(llm.time, "sleep", fake.sleep)
    return fake


def test_the_sixth_request_in_a_minute_waits_for_the_window(clock: FakeClock) -> None:
    for _ in range(5):
        llm._LIMITER.acquire("model-a", 5)
        clock.now += 1
    assert clock.slept == []

    llm._LIMITER.acquire("model-a", 5)

    # The first request went out at 1000; the sixth may go at 1060.
    assert clock.slept == [55.0]
    assert clock.now == 1060.0


def test_two_models_are_limited_separately(clock: FakeClock) -> None:
    for _ in range(5):
        llm._LIMITER.acquire("model-a", 5)
        llm._LIMITER.acquire("model-b", 5)
    assert clock.slept == []


def test_zero_means_no_limit(clock: FakeClock) -> None:
    for _ in range(50):
        llm._LIMITER.acquire("model-a", 0)
    assert clock.slept == []


def test_every_retry_passes_the_limiter(
    clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    replies = [httpx.Response(503, json={}), httpx.Response(503, json={})]
    replies.append(httpx.Response(200, json={}))
    sent: list[float] = []

    def post(url: str, **_kwargs: object) -> httpx.Response:
        sent.append(clock.now)
        return replies[len(sent) - 1]

    monkeypatch.setattr(llm.httpx, "post", post)
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    monkeypatch.setattr(llm, "get_settings", lambda: settings)

    response = llm._post("https://model.invalid/x", model="model-a", rpm=2)

    assert response.status_code == 200
    assert len(sent) == 3
    # Two attempts fill the minute, so the third waits for the window, not just the
    # backoff: no 60-second span ever holds more than two.
    assert sent[2] - sent[0] >= 60


def test_a_retry_honours_the_retry_after_google_sends(
    clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    busy = {
        "error": {
            "code": 429,
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.RetryInfo",
                    "retryDelay": "7s",
                }
            ],
        }
    }
    replies = [
        httpx.Response(429, json=busy),
        httpx.Response(503, json={}, headers={"retry-after": "12"}),
        httpx.Response(200, json={}),
    ]
    monkeypatch.setattr(llm.httpx, "post", lambda url, **_k: replies.pop(0))
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    monkeypatch.setattr(llm, "get_settings", lambda: settings)

    assert (
        llm._post("https://model.invalid/x", model="model-a", rpm=0).status_code == 200
    )
    assert clock.slept == [7.0, 12.0]


def test_the_limit_for_each_role_comes_from_config() -> None:
    settings = Settings(_env_file=None, extract_rpm=5, merge_rpm=3)  # type: ignore[call-arg]
    assert (settings.extract_rpm, settings.merge_rpm) == (5, 3)
    assert Settings(_env_file=None).extract_rpm == 0  # type: ignore[call-arg]


def test_calls_through_a_provider_pass_the_limit_for_their_role(
    clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        llm_provider="gemini",
        llm_api_key="invented-key",
        extract_model="invented-model",
        extract_price_in=1,
        extract_price_out=1,
        extract_rpm=1,
    )
    monkeypatch.setattr(llm, "get_settings", lambda: settings)
    answer = {
        "candidates": [{"content": {"parts": [{"text": '{"value": 1}'}]}}],
        "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1},
    }
    sent: list[float] = []

    def post(url: str, **_kwargs: object) -> httpx.Response:
        sent.append(clock.now)
        return httpx.Response(200, json=answer)

    monkeypatch.setattr(llm.httpx, "post", post)

    class _Out(BaseModel):
        value: int

    request = llm.ModelRequest(
        purpose="test",
        role="extract",
        prompt=llm.Prompt(name="test", version="1", text="Invented."),
        user_text="Invented.",
        output=_Out,
    )
    llm._execute(request)
    llm._execute(request)

    assert len(sent) == 2 and sent[1] - sent[0] >= 60
