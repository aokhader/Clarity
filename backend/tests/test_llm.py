from pathlib import Path

import httpx
import pytest
from pydantic import BaseModel

from app.config import get_settings
from app.digest import llm


class _Out(BaseModel):
    value: int


def test_a_model_call_without_prices_is_refused(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("EXTRACT_MODEL", "test-model")
    for name in ("EXTRACT_PRICE_IN", "EXTRACT_PRICE_OUT"):
        monkeypatch.setenv(name, "")
    get_settings.cache_clear()
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
    for name, value in {
        "LLM_API_KEY": "test-key",
        "EXTRACT_MODEL": "test-model",
        "EXTRACT_PRICE_IN": "1",
        "EXTRACT_PRICE_OUT": "5",
    }.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
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
