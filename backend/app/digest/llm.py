"""The single path to the models: cached, costed, schema-checked.

Every call is keyed by model, prompt name and version, output schema, and input content.
A key seen before is answered from `llm_calls` with no request. Every call, hit or miss,
writes an `llm_calls` row, which is where the cost-per-case figure comes from.

Database work stays on the calling thread. Only the HTTP requests run concurrently.
"""

import base64
import hashlib
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import LlmCall

log = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"
ANTHROPIC_VERSION = "2023-06-01"
TOOL_NAME = "record_output"
TOOL_INSTRUCTION = (
    f"Give your answer only by calling the {TOOL_NAME} tool, exactly once, "
    "with input that matches its schema."
)
REQUEST_TIMEOUT_SECONDS = 180
# Rate limits, overload, and dropped connections are retried with backoff; anything
# else fails the one call and is recorded, and the next digest run tries it again.
RETRY_STATUSES = {429, 500, 502, 503, 504, 529}
MAX_ATTEMPTS = 5

Role = Literal["extract", "merge"]


class ModelsNotConfigured(Exception):
    pass


class ExtractionFailed(Exception):
    pass


class NoStructuredOutput(ExtractionFailed):
    """The model answered without a usable tool call; the tokens were still billed."""

    def __init__(self, message: str, tokens_in: int, tokens_out: int) -> None:
        super().__init__(message)
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    text: str


@lru_cache
def load_prompt(name: str) -> Prompt:
    """Prompt files start with a `version: N` line, which is part of the cache key."""
    raw = (PROMPTS_DIR / f"{name}.txt").read_text(encoding="utf-8")
    first, _, rest = raw.partition("\n")
    if not first.startswith("version:"):
        raise ValueError(f"Prompt {name} must start with a version line")
    return Prompt(name=name, version=first.split(":", 1)[1].strip(), text=rest.strip())


@dataclass
class ModelRequest:
    purpose: str
    role: Role
    prompt: Prompt
    user_text: str
    output: type[BaseModel]
    images: list[bytes] = field(default_factory=list)
    matter_id: int | None = None
    source_id: int | None = None
    page_no: int | None = None

    @property
    def model(self) -> str:
        settings = get_settings()
        name = (
            settings.extract_model if self.role == "extract" else settings.merge_model
        )
        if not name:
            raise ModelsNotConfigured("Set EXTRACT_MODEL and MERGE_MODEL in .env")
        return name

    @property
    def cache_key(self) -> str:
        digest = hashlib.sha256()
        for part in (
            self.model,
            self.prompt.name,
            self.prompt.version,
            self.output.__name__,
            self.user_text,
        ):
            digest.update(part.encode("utf-8"))
            digest.update(b"\x00")
        for image in self.images:
            digest.update(hashlib.sha256(image).digest())
        return digest.hexdigest()


@dataclass
class ModelResult:
    data: dict[str, Any] | None
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None


def run_batch(session: Session, requests: list[ModelRequest]) -> list[BaseModel | None]:
    """Answer each request from the cache or the model, in order. None means it failed."""
    if not requests:
        return []
    results: list[BaseModel | None] = [None] * len(requests)
    misses: list[int] = []
    for index, request in enumerate(requests):
        cached = _lookup(session, request)
        if cached is not None:
            results[index] = cached
        else:
            misses.append(index)
    if misses:
        workers = get_settings().extract_concurrency
        with ThreadPoolExecutor(max_workers=workers) as pool:
            outcomes = list(pool.map(lambda i: _execute(requests[i]), misses))
        for index, outcome in zip(misses, outcomes, strict=True):
            results[index] = _record(session, requests[index], outcome)
    session.commit()
    return results


def call(session: Session, request: ModelRequest) -> BaseModel | None:
    return run_batch(session, [request])[0]


def _lookup(session: Session, request: ModelRequest) -> BaseModel | None:
    key = request.cache_key
    hit = session.scalars(
        select(LlmCall)
        .where(LlmCall.cache_key == key, LlmCall.response_json.is_not(None))
        .order_by(LlmCall.id.desc())
    ).first()
    if hit is None or hit.response_json is None:
        return None
    try:
        parsed = request.output.model_validate(hit.response_json)
    except ValidationError:
        return None
    session.add(
        LlmCall(
            matter_id=request.matter_id,
            purpose=request.purpose,
            model=hit.model,
            cache_key=key,
            cache_hit=True,
            source_id=request.source_id,
            page_no=request.page_no,
        )
    )
    return parsed


def _record(
    session: Session, request: ModelRequest, outcome: ModelResult
) -> BaseModel | None:
    parsed: BaseModel | None = None
    if outcome.data is not None:
        parsed = request.output.model_validate(outcome.data)
    session.add(
        LlmCall(
            matter_id=request.matter_id,
            purpose=request.purpose,
            model=request.model,
            cache_key=request.cache_key,
            response_json=outcome.data,
            input_tokens=outcome.input_tokens,
            output_tokens=outcome.output_tokens,
            cost_micro_usd=_cost_micro_usd(request.role, outcome),
            source_id=request.source_id,
            page_no=request.page_no,
            error=outcome.error,
        )
    )
    if outcome.error:
        log.warning(
            "%s failed (source %s page %s): %s",
            request.purpose,
            request.source_id,
            request.page_no,
            outcome.error[:200],
        )
    return parsed


def _execute(request: ModelRequest) -> ModelResult:
    """Call the model; on a schema failure or a missing tool call, ask once more."""
    total_in = total_out = 0
    feedback: str | None = None
    for _attempt in range(2):
        try:
            data, tokens_in, tokens_out = _send(request, feedback)
        except NoStructuredOutput as error:
            total_in += error.tokens_in
            total_out += error.tokens_out
            feedback = f"Your previous answer had {error}. {TOOL_INSTRUCTION}"
            continue
        except (httpx.HTTPError, ExtractionFailed, ValueError) as error:
            return ModelResult(
                None, total_in, total_out, f"{type(error).__name__}: {error}"
            )
        total_in += tokens_in
        total_out += tokens_out
        try:
            validated = request.output.model_validate(data)
        except ValidationError as error:
            feedback = f"Your previous output did not match the schema: {error}"[:2000]
            continue
        return ModelResult(validated.model_dump(mode="json"), total_in, total_out)
    return ModelResult(None, total_in, total_out, f"no valid output: {feedback}")


def _send(request: ModelRequest, feedback: str | None) -> tuple[Any, int, int]:
    settings = get_settings()
    if settings.llm_api_key is None:
        raise ModelsNotConfigured("Set LLM_API_KEY in .env")
    # The cost-per-case figure must be real: a call with no price would count as $0.
    prefix = request.role.upper()
    if None in _prices(request.role):
        raise ModelsNotConfigured(
            f"Set {prefix}_PRICE_IN and {prefix}_PRICE_OUT in .env"
        )
    user_text = (
        request.user_text if feedback is None else f"{request.user_text}\n\n{feedback}"
    )
    schema = _inline_refs(request.output.model_json_schema())
    if settings.llm_provider == "openai":
        return _send_openai(request, user_text, schema)
    return _send_anthropic(request, user_text, schema)


def _send_anthropic(
    request: ModelRequest, user_text: str, schema: dict[str, Any]
) -> tuple[Any, int, int]:
    settings = get_settings()
    assert settings.llm_api_key is not None
    content: list[dict[str, Any]] = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": base64.b64encode(image).decode("ascii"),
            },
        }
        for image in request.images
    ]
    content.append({"type": "text", "text": user_text})
    # The output comes back as the input of one tool call. Current Claude models reject
    # a forced `tool_choice`, so the call is requested in the system prompt instead,
    # and `_execute` asks again when it is missing.
    body = {
        "model": request.model,
        "max_tokens": settings.llm_max_output_tokens,
        "system": f"{request.prompt.text}\n\n{TOOL_INSTRUCTION}",
        "messages": [{"role": "user", "content": content}],
        "tools": [
            {
                "name": TOOL_NAME,
                "description": "Record the result.",
                "input_schema": schema,
            }
        ],
        "tool_choice": {"type": "auto"},
    }
    response = _post(
        f"{settings.llm_endpoint}/messages",
        json=body,
        headers={
            "x-api-key": settings.llm_api_key.get_secret_value(),
            "anthropic-version": ANTHROPIC_VERSION,
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if response.status_code >= 400:
        raise ExtractionFailed(f"HTTP {response.status_code}: {response.text[:300]}")
    payload = response.json()
    usage = payload.get("usage") or {}
    tokens_in = int(usage.get("input_tokens", 0))
    tokens_out = int(usage.get("output_tokens", 0))
    stop_reason = payload.get("stop_reason")
    blocks = [b for b in payload.get("content", []) if b.get("type") == "tool_use"]
    if stop_reason in ("max_tokens", "refusal") or not blocks:
        # Paid for even though unusable, so the tokens still go into the cost figure.
        raise NoStructuredOutput(
            f"no {TOOL_NAME} call (stop_reason {stop_reason})", tokens_in, tokens_out
        )
    return blocks[0].get("input"), tokens_in, tokens_out


def _send_openai(
    request: ModelRequest, user_text: str, schema: dict[str, Any]
) -> tuple[Any, int, int]:
    settings = get_settings()
    assert settings.llm_api_key is not None
    content: list[dict[str, Any]] = [
        {
            "type": "image_url",
            "image_url": {
                "url": "data:image/png;base64,"
                + base64.b64encode(image).decode("ascii")
            },
        }
        for image in request.images
    ]
    content.append({"type": "text", "text": user_text})
    system = (
        f"{request.prompt.text}\n\nRespond with one JSON object that matches this JSON "
        f"Schema, and nothing else:\n{json.dumps(schema)}"
    )
    body = {
        "model": request.model,
        "max_completion_tokens": settings.llm_max_output_tokens,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ],
    }
    response = _post(
        f"{settings.llm_endpoint}/chat/completions",
        json=body,
        headers={"Authorization": f"Bearer {settings.llm_api_key.get_secret_value()}"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if response.status_code >= 400:
        raise ExtractionFailed(f"HTTP {response.status_code}: {response.text[:300]}")
    payload = response.json()
    usage = payload.get("usage") or {}
    text = payload["choices"][0]["message"].get("content") or "{}"
    return (
        json.loads(text),
        int(usage.get("prompt_tokens", 0)),
        int(usage.get("completion_tokens", 0)),
    )


def _post(url: str, **kwargs: Any) -> httpx.Response:
    """POST, retrying rate limits, overload, and dropped connections with backoff."""
    for attempt in range(MAX_ATTEMPTS):
        last = attempt + 1 == MAX_ATTEMPTS
        try:
            response = httpx.post(url, **kwargs)
        except httpx.TransportError:
            if last:
                raise
            time.sleep(min(2**attempt, 30))
            continue
        if response.status_code not in RETRY_STATUSES or last:
            return response
        retry_after = response.headers.get("retry-after", "")
        wait = float(retry_after) if retry_after.isdigit() else min(2**attempt, 30)
        log.info("Model API %s; retrying in %.0fs", response.status_code, wait)
        time.sleep(wait)
    raise AssertionError("unreachable")


def _cost_micro_usd(role: Role, outcome: ModelResult) -> int:
    """USD per million tokens times tokens is exactly micro-dollars."""
    price_in, price_out = _prices(role)
    total = Decimal(outcome.input_tokens) * (price_in or Decimal(0)) + Decimal(
        outcome.output_tokens
    ) * (price_out or Decimal(0))
    return int(total.to_integral_value())


def _prices(role: Role) -> tuple[Decimal | None, Decimal | None]:
    """USD per million input and output tokens for the model that plays this role."""
    settings = get_settings()
    if role == "extract":
        return settings.extract_price_in, settings.extract_price_out
    return settings.merge_price_in, settings.merge_price_out


def _inline_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """Replace `$ref`s with their definitions; some model APIs reject `$defs`."""
    definitions = schema.get("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                name = str(node["$ref"]).rsplit("/", 1)[-1]
                return resolve(definitions[name])
            return {k: resolve(v) for k, v in node.items() if k != "$defs"}
        if isinstance(node, list):
            return [resolve(item) for item in node]
        return node

    return resolve(schema)
