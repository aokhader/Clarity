"""No more model requests per minute than config allows, per model (D31).

Every HTTP attempt counts, the first try and each retry alike, and attempts are spaced
evenly, so a burst of quick retries cannot fill a minute early. A wait the API asks
for beyond a cap fails the call instead of stalling the run. A fake clock stands in
for time, so the tests never wait.
"""

from itertools import pairwise

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


def _most_in_any_minute(times: list[float]) -> int:
    # Closed at both ends: the API counted an attempt exactly 60 s after another.
    return max(sum(1 for t in times if start <= t <= start + 60) for start in times)


def test_attempts_to_one_model_are_spaced_evenly(clock: FakeClock) -> None:
    sent = []
    for _ in range(6):
        llm._LIMITER.acquire("model-a", 5, margin=1.0)
        sent.append(clock.now)

    # 60 / 5 = 12 seconds apart, plus the one-second margin.
    assert clock.slept == [13.0] * 5
    assert _most_in_any_minute(sent) == 5


def test_two_models_are_limited_separately(clock: FakeClock) -> None:
    llm._LIMITER.acquire("model-a", 5, margin=1.0)
    llm._LIMITER.acquire("model-b", 5, margin=1.0)
    assert clock.slept == []

    llm._LIMITER.acquire("model-a", 5, margin=1.0)
    llm._LIMITER.acquire("model-b", 5, margin=1.0)
    # Model b waited out its own interval while model a slept, so it goes at once.
    assert clock.slept == [13.0]


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
    # At 2 a minute, each retry waits its 30-second slot, not just the short backoff.
    assert all(later - earlier >= 30 for earlier, later in pairwise(sent))


def test_quick_retries_cannot_put_six_attempts_in_a_minute(
    clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The trial's failure: overload answered fast, so retries went 1, 2 and 4 s apart.
    sent: list[float] = []

    def overloaded(url: str, **_kwargs: object) -> httpx.Response:
        sent.append(clock.now)
        return httpx.Response(503, json={})

    monkeypatch.setattr(llm.httpx, "post", overloaded)
    settings = Settings(_env_file=None, llm_max_attempts=12)  # type: ignore[call-arg]
    monkeypatch.setattr(llm, "get_settings", lambda: settings)

    llm._post("https://model.invalid/x", model="model-a", rpm=5)

    assert len(sent) == 12
    assert _most_in_any_minute(sent) <= 5


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


def _over_quota(delay: str, quota: str) -> dict:
    return {
        "error": {
            "code": 429,
            # As long as the API's own, so the quota id lies past any cut of the text.
            "message": "Invented quota message. " * 20,
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                    "violations": [
                        {"quotaMetric": "invented-metric", "quotaId": quota}
                    ],
                },
                {
                    "@type": "type.googleapis.com/google.rpc.RetryInfo",
                    "retryDelay": delay,
                },
            ],
        }
    }


def test_a_wait_longer_than_the_cap_fails_the_call_at_once(
    clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[float] = []

    def over_quota(url: str, **_kwargs: object) -> httpx.Response:
        sent.append(clock.now)
        return httpx.Response(429, json=_over_quota("1500s", "InventedPerDayQuota"))

    monkeypatch.setattr(llm.httpx, "post", over_quota)
    settings = Settings(_env_file=None, llm_max_retry_wait_seconds=120)  # type: ignore[call-arg]
    monkeypatch.setattr(llm, "get_settings", lambda: settings)

    with pytest.raises(llm.RetryWaitTooLong) as raised:
        llm._post("https://model.invalid/x", model="model-a", rpm=0)

    assert len(sent) == 1 and clock.slept == []
    message = str(raised.value)
    assert "1500" in message and "120" in message
    assert "InventedPerDayQuota" in message


def test_a_retry_after_header_past_the_cap_fails_too(
    clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    reply = httpx.Response(503, json={}, headers={"retry-after": "600"})
    monkeypatch.setattr(llm.httpx, "post", lambda url, **_k: reply)
    settings = Settings(_env_file=None, llm_max_retry_wait_seconds=120)  # type: ignore[call-arg]
    monkeypatch.setattr(llm, "get_settings", lambda: settings)

    with pytest.raises(llm.RetryWaitTooLong, match="600"):
        llm._post("https://model.invalid/x", model="model-a", rpm=0)
    assert clock.slept == []


def test_a_failed_call_records_the_quota_it_ran_into(
    clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        llm_provider="gemini",
        llm_api_key="invented-key",
        extract_model="invented-model",
        extract_price_in=1,
        extract_price_out=1,
        llm_max_attempts=1,
    )
    monkeypatch.setattr(llm, "get_settings", lambda: settings)
    body = _over_quota("30s", "InventedPerMinuteQuota")
    monkeypatch.setattr(
        llm.httpx, "post", lambda url, **_k: httpx.Response(429, json=body)
    )

    class _Out(BaseModel):
        value: int

    result = llm._execute(
        llm.ModelRequest(
            purpose="test",
            role="extract",
            prompt=llm.Prompt(name="test", version="1", text="Invented."),
            user_text="Invented.",
            output=_Out,
        )
    )

    assert result.error is not None and "HTTP 429" in result.error
    assert "InventedPerMinuteQuota" in result.error


def test_the_pacing_margin_and_the_wait_cap_come_from_config() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.llm_rate_margin_seconds == 1.0
    assert settings.llm_max_retry_wait_seconds == 120
