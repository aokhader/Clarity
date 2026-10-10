"""The `gemini` provider: Google's native generateContent API, over httpx (D30).

Settings are built without the .env file, so the real key and endpoint never reach a
test, and every request goes through an httpx mock transport.
"""

import base64
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import BaseModel

from app.config import Settings
from app.digest import llm

KEY = "invented-key-123"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8


class _Item(BaseModel):
    label: str
    count: int | None = None


class _Out(BaseModel):
    items: list[_Item]
    extra: dict[str, Any] = {}


def _request(images: list[bytes] | None = None) -> llm.ModelRequest:
    return llm.ModelRequest(
        purpose="test",
        role="extract",
        prompt=llm.Prompt(name="test", version="1", text="Invented instructions."),
        user_text="Invented input.",
        output=_Out,
        images=images or [],
    )


def _answer(
    data: dict[str, Any] | None,
    usage: dict[str, int] | None = None,
    thought: str | None = None,
) -> dict[str, Any]:
    parts: list[dict[str, Any]] = []
    if thought is not None:
        parts.append({"text": thought, "thought": True})
    if data is not None:
        parts.append({"text": json.dumps(data)})
    candidates = [{"content": {"role": "model", "parts": parts}}] if parts else []
    return {
        "candidates": candidates,
        "usageMetadata": usage or {"promptTokenCount": 10, "candidatesTokenCount": 2},
    }


@pytest.fixture
def gemini(data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        llm_provider="gemini",
        llm_api_key=KEY,
        extract_model="gemini-invented",
        extract_price_in="1",
        extract_price_out="1",
    )
    monkeypatch.setattr(llm, "get_settings", lambda: settings)
    monkeypatch.setattr(llm.time, "sleep", lambda _s: None)
    return settings


def _route(
    monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response]
) -> list[httpx.Request]:
    sent: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return handler(request)

    client = httpx.Client(transport=httpx.MockTransport(record))
    monkeypatch.setattr(llm.httpx, "post", client.post)
    return sent


def test_the_endpoint_defaults_to_googles_for_gemini(gemini: Settings) -> None:
    assert gemini.llm_endpoint == "https://generativelanguage.googleapis.com/v1beta"


def test_a_request_has_the_key_in_a_header_the_schema_and_the_image(
    gemini: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _route(
        monkeypatch, lambda _r: httpx.Response(200, json=_answer({"items": []}))
    )

    llm._execute(_request([PNG]))

    request = sent[0]
    assert str(request.url) == (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-invented:generateContent"
    )
    assert request.headers["x-goog-api-key"] == KEY
    assert KEY not in str(request.url)
    body = json.loads(request.content)
    assert body["systemInstruction"] == {"parts": [{"text": "Invented instructions."}]}
    [content] = body["contents"]
    assert content["role"] == "user"
    image, text = content["parts"]
    assert image["inline_data"]["mime_type"] == "image/png"
    assert base64.b64decode(image["inline_data"]["data"]) == PNG
    assert text == {"text": "Invented input."}
    config = body["generationConfig"]
    assert config["responseMimeType"] == "application/json"
    schema = config["responseJsonSchema"]
    assert "$defs" not in json.dumps(schema)
    assert schema["properties"]["items"]["items"]["properties"]["label"]["type"] == (
        "string"
    )


def test_the_answer_is_read_from_the_parts_and_thoughts_are_skipped(
    gemini: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = {"items": [{"label": "invented", "count": 2}]}
    _route(
        monkeypatch,
        lambda _r: httpx.Response(
            200, json=_answer(data, thought="Invented thinking.")
        ),
    )

    result = llm._execute(_request())

    assert result.error is None
    assert result.data == {"items": [{"label": "invented", "count": 2}], "extra": {}}


def test_thinking_tokens_count_as_output(
    gemini: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    usage = {
        "promptTokenCount": 100,
        "candidatesTokenCount": 20,
        "thoughtsTokenCount": 30,
    }
    _route(
        monkeypatch, lambda _r: httpx.Response(200, json=_answer({"items": []}, usage))
    )

    result = llm._execute(_request())

    assert (result.input_tokens, result.output_tokens) == (100, 50)


def test_overload_is_retried_then_answered(
    gemini: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    replies = [
        httpx.Response(503, json={"error": {"message": "overloaded"}}),
        httpx.Response(200, json=_answer({"items": []})),
    ]
    sent = _route(monkeypatch, lambda _r: replies[min(len(sent) - 1, 1)])

    result = llm._execute(_request())

    assert result.error is None and len(sent) == 2


def test_an_error_is_recorded_without_the_key(
    gemini: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = {"error": {"code": 403, "message": f"Invented refusal for key {KEY}"}}
    _route(monkeypatch, lambda _r: httpx.Response(403, json=body))

    result = llm._execute(_request())

    assert result.data is None
    assert result.error is not None and "HTTP 403" in result.error
    assert KEY not in result.error


def test_an_answer_with_no_usable_text_is_asked_for_again(
    gemini: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    replies = [
        httpx.Response(200, json=_answer(None)),  # blocked: no candidates
        httpx.Response(200, json=_answer({"items": []})),
    ]
    sent = _route(monkeypatch, lambda _r: replies[min(len(sent) - 1, 1)])

    result = llm._execute(_request())

    assert result.error is None and len(sent) == 2
    assert result.input_tokens == 20  # both calls are paid for


def test_a_rejected_json_schema_falls_back_to_the_openapi_schema(
    gemini: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    rejected = {
        "error": {
            "code": 400,
            "message": 'Invalid JSON payload received. Unknown name "responseJsonSchema"',
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        config = json.loads(request.content)["generationConfig"]
        if "responseJsonSchema" in config:
            return httpx.Response(400, json=rejected)
        return httpx.Response(200, json=_answer({"items": []}))

    sent = _route(monkeypatch, handler)

    result = llm._execute(_request())

    assert result.error is None and len(sent) == 2
    schema = json.loads(sent[1].content)["generationConfig"]["responseSchema"]
    flat = json.dumps(schema)
    for unsupported in ('"title"', '"additionalProperties"', '"default"', '"null"'):
        assert unsupported not in flat
    count = schema["properties"]["items"]["items"]["properties"]["count"]
    assert count == {"type": "integer", "nullable": True}
