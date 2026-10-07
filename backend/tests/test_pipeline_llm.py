"""What `llm.py` sends and logs: each image with its own media type, and no case text
in the warning log."""

import logging
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.digest import llm

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
CASE_TEXT = "Invented case words that must stay out of the log"
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 8


class _Out(BaseModel):
    value: int


def _request(images: list[bytes]) -> llm.ModelRequest:
    return llm.ModelRequest(
        purpose="test",
        role="extract",
        prompt=llm.Prompt(name="test", version="1", text="Return a value."),
        user_text="input",
        output=_Out,
        images=images,
    )


@pytest.fixture
def configured(data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in {
        "LLM_API_KEY": "test-key",
        "EXTRACT_MODEL": "test-model",
        "EXTRACT_PRICE_IN": "1",
        "EXTRACT_PRICE_OUT": "1",
    }.items():
        monkeypatch.setenv(name, value)


def _capture(monkeypatch: pytest.MonkeyPatch, reply: dict[str, Any]) -> list[dict]:
    bodies: list[dict] = []

    def fake_post(url: str, json: dict, **_kwargs: object) -> httpx.Response:
        bodies.append(json)
        return httpx.Response(200, json=reply)

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    return bodies


ANTHROPIC_REPLY = {
    "stop_reason": "tool_use",
    "content": [{"type": "tool_use", "name": llm.TOOL_NAME, "input": {"value": 1}}],
    "usage": {"input_tokens": 1, "output_tokens": 1},
}
OPENAI_REPLY = {
    "choices": [{"message": {"content": '{"value": 1}'}}],
    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
}


def test_each_image_goes_to_anthropic_with_its_own_media_type(
    configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    get_settings.cache_clear()
    bodies = _capture(monkeypatch, ANTHROPIC_REPLY)

    llm._execute(_request([PNG, JPEG]))

    images = [b for b in bodies[0]["messages"][0]["content"] if b["type"] == "image"]
    assert [i["source"]["media_type"] for i in images] == ["image/png", "image/jpeg"]


def test_each_image_goes_to_openai_with_its_own_media_type(
    configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    get_settings.cache_clear()
    bodies = _capture(monkeypatch, OPENAI_REPLY)

    llm._execute(_request([PNG, JPEG]))

    urls = [
        b["image_url"]["url"]
        for b in bodies[0]["messages"][1]["content"]
        if b["type"] == "image_url"
    ]
    assert urls[0].startswith("data:image/png;base64,")
    assert urls[1].startswith("data:image/jpeg;base64,")


def test_a_failed_call_logs_no_case_text(
    data_dir: Path,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("EXTRACT_MODEL", "test-model")
    get_settings.cache_clear()

    def failing(_request: llm.ModelRequest) -> llm.ModelResult:
        # A schema failure message quotes the model's input back, case text included.
        return llm.ModelResult(
            None, 1, 1, f"no valid output: input_value='{CASE_TEXT}'"
        )

    monkeypatch.setattr(llm, "_execute", failing)
    with caplog.at_level(logging.INFO, logger="app.digest.llm"):
        llm.run_batch(session, [_request([])])

    assert caplog.records, "the failure is still logged"
    assert CASE_TEXT not in caplog.text
