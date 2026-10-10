from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from pydantic import BaseModel

from app.config import Settings
from app.digest import llm


class _Out(BaseModel):
    value: int


def test_a_model_call_without_prices_is_refused(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Built without the .env file, so prices filled in there cannot leak in.
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        llm_api_key="test-key",
        extract_model="test-model",
    )
    monkeypatch.setattr(llm, "get_settings", lambda: settings)
    request = llm.ModelRequest(
        purpose="test",
        role="extract",
        prompt=llm.Prompt(name="test", version="1", text="Return a value."),
        user_text="input",
        output=_Out,
    )
    with pytest.raises(llm.ModelsNotConfigured, match="EXTRACT_PRICE_IN"):
        llm._send(request, None)


def test_a_missing_tool_call_is_asked_again_and_its_tokens_are_counted(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Built without the .env file: the provider under test is anthropic, whatever
    # the developer's own settings say.
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        llm_provider="anthropic",
        llm_api_key="test-key",
        extract_model="test-model",
        extract_price_in=Decimal(1),
        extract_price_out=Decimal(5),
    )
    monkeypatch.setattr(llm, "get_settings", lambda: settings)
    bodies: list[dict[str, object]] = []
    replies = [
        {"stop_reason": "end_turn", "content": [{"type": "text", "text": "Done."}]},
        {
            "stop_reason": "tool_use",
            "content": [
                {"type": "tool_use", "name": llm.TOOL_NAME, "input": {"value": 3}}
            ],
        },
    ]

    def fake_post(
        url: str, json: dict[str, object], **_kwargs: object
    ) -> httpx.Response:
        bodies.append(json)
        reply = {
            **replies[len(bodies) - 1],
            "usage": {"input_tokens": 100, "output_tokens": 10},
        }
        return httpx.Response(200, json=reply)

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    request = llm.ModelRequest(
        purpose="test",
        role="extract",
        prompt=llm.Prompt(name="test", version="1", text="Return a value."),
        user_text="input",
        output=_Out,
    )
    result = llm._execute(request)
    assert result.data == {"value": 3}
    assert (result.input_tokens, result.output_tokens) == (200, 20)
    assert all(body["tool_choice"] == {"type": "auto"} for body in bodies)


def test_rate_limits_and_dropped_connections_are_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcomes: list[object] = [
        httpx.ConnectError("reset"),
        httpx.Response(429, headers={"retry-after": "2"}),
        httpx.Response(200, json={}),
    ]
    sleeps: list[float] = []

    def fake_post(url: str, **_kwargs: object) -> httpx.Response:
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        assert isinstance(outcome, httpx.Response)
        return outcome

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    monkeypatch.setattr(llm.time, "sleep", sleeps.append)
    # The default retry count, not whatever the developer's .env sets.
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    monkeypatch.setattr(llm, "get_settings", lambda: settings)
    assert llm._post("https://example.invalid/messages").status_code == 200
    assert sleeps == [1, 2.0]
