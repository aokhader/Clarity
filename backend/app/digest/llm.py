"""The single path to the models: cached, costed, schema-checked.

Every call is keyed by model, prompt name and version, output schema, and input content.
A key seen before is answered from `llm_calls` with no request. Every call, hit or miss,
writes an `llm_calls` row, which is where the cost-per-case figure comes from.

A key whose last call failed is answered with that failure, not sent again, so a second
digest over unchanged inputs costs nothing. The failure stays counted on every run
until `retrying_failed_calls` (`cli digest --retry-failed`) asks the model again.

Database work stays on the calling thread. Only the HTTP requests run concurrently.
"""

import base64
import hashlib
import json
import logging
import re
import threading
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import ContextVar
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
_retry_failed: ContextVar[bool] = ContextVar("retry_failed", default=False)
ANTHROPIC_VERSION = "2023-06-01"
TOOL_NAME = "record_output"
TOOL_INSTRUCTION = (
    f"Give your answer only by calling the {TOOL_NAME} tool, exactly once, "
    "with input that matches its schema."
)
# Rate limits, overload, and dropped connections are retried with backoff, up to
# `llm_max_attempts`; anything else fails the one call, which is recorded and cached
# as failed until `cli digest --retry-failed`.
RETRY_STATUSES = {429, 500, 502, 503, 504, 529}

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
        found, cached = _lookup(session, request)
        if found:
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


@contextmanager
def retrying_failed_calls() -> Iterator[None]:
    """Within the block, a request whose last call failed goes to the model again."""
    token = _retry_failed.set(True)
    try:
        yield
    finally:
        _retry_failed.reset(token)


def _lookup(session: Session, request: ModelRequest) -> tuple[bool, BaseModel | None]:
    """(found, result) from earlier calls. A cached failure is found, with no result."""
    key = request.cache_key
    hit = session.scalars(
        select(LlmCall)
        .where(LlmCall.cache_key == key, LlmCall.response_json.is_not(None))
        .order_by(LlmCall.id.desc())
    ).first()
    if hit is not None and hit.response_json is not None:
        try:
            parsed = request.output.model_validate(hit.response_json)
        except ValidationError:
            return False, None
        _record_hit(session, request, hit.model, None)
        return True, parsed
    if _retry_failed.get():
        return False, None
    failed = session.scalars(
        select(LlmCall)
        .where(
            LlmCall.cache_key == key,
            LlmCall.cache_hit.is_(False),
            LlmCall.error.is_not(None),
        )
        .order_by(LlmCall.id.desc())
    ).first()
    if failed is None:
        return False, None
    _record_hit(session, request, failed.model, f"earlier call failed: {failed.error}")
    return True, None


def _record_hit(
    session: Session, request: ModelRequest, model: str, error: str | None
) -> None:
    session.add(
        LlmCall(
            matter_id=request.matter_id,
            purpose=request.purpose,
            model=model,
            cache_key=request.cache_key,
            cache_hit=True,
            source_id=request.source_id,
            page_no=request.page_no,
            error=error[:2000] if error else None,
        )
    )


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
        # Only the kind of error: its text can quote the model's input or output, which
        # is case text. The full error is in the llm_calls row.
        log.warning(
            "%s failed (source %s page %s): %s; details in llm_calls",
            request.purpose,
            request.source_id,
            request.page_no,
            outcome.error.split(":", 1)[0][:60],
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
            feedback = f"Your previous answer had {error}. {_answer_instruction()}"
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
    if settings.llm_provider == "gemini":
        return _send_gemini(request, user_text, schema)
    return _send_anthropic(request, user_text, schema)


def _answer_instruction() -> str:
    if get_settings().llm_provider == "anthropic":
        return TOOL_INSTRUCTION
    return "Answer with one JSON object that matches the schema, and nothing else."


JPEG_MAGIC = bytes.fromhex("ffd8ff")


def media_type(image: bytes) -> str:
    """Pages are rendered as PNG; a document that is itself a photo may be a JPEG."""
    return "image/jpeg" if image.startswith(JPEG_MAGIC) else "image/png"


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
                "media_type": media_type(image),
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
        model=request.model,
        rpm=_rpm(request.role),
        json=body,
        headers={
            "x-api-key": settings.llm_api_key.get_secret_value(),
            "anthropic-version": ANTHROPIC_VERSION,
        },
        timeout=settings.llm_timeout_seconds,
    )
    if response.status_code >= 400:
        raise ExtractionFailed(_http_error(response))
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
                "url": f"data:{media_type(image)};base64,"
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
        model=request.model,
        rpm=_rpm(request.role),
        json=body,
        headers={"Authorization": f"Bearer {settings.llm_api_key.get_secret_value()}"},
        timeout=settings.llm_timeout_seconds,
    )
    if response.status_code >= 400:
        raise ExtractionFailed(_http_error(response))
    payload = response.json()
    usage = payload.get("usage") or {}
    text = payload["choices"][0]["message"].get("content") or "{}"
    return (
        json.loads(text),
        int(usage.get("prompt_tokens", 0)),
        int(usage.get("completion_tokens", 0)),
    )


def _send_gemini(
    request: ModelRequest, user_text: str, schema: dict[str, Any]
) -> tuple[Any, int, int]:
    """Google's generateContent, with the output constrained to the request's schema.

    The key travels in a header, never in the URL, which proxies and logs record.
    """
    settings = get_settings()
    assert settings.llm_api_key is not None
    key = settings.llm_api_key.get_secret_value()
    parts: list[dict[str, Any]] = [
        {
            "inline_data": {
                "mime_type": media_type(image),
                "data": base64.b64encode(image).decode("ascii"),
            }
        }
        for image in request.images
    ]
    parts.append({"text": user_text})
    body: dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": request.prompt.text}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseJsonSchema": schema,
            "maxOutputTokens": settings.llm_max_output_tokens,
        },
    }
    url = f"{settings.llm_endpoint}/models/{request.model}:generateContent"
    headers = {"x-goog-api-key": key}
    response = _post(
        url,
        model=request.model,
        rpm=_rpm(request.role),
        json=body,
        headers=headers,
        timeout=settings.llm_timeout_seconds,
    )
    if response.status_code == 400 and "responseJsonSchema" in response.text:
        # The older field takes only an OpenAPI subset of JSON Schema.
        openapi, stripped = _openapi_schema(schema)
        log.warning(
            "Gemini rejected responseJsonSchema; using responseSchema without %s",
            ", ".join(sorted(stripped)) or "no keywords",
        )
        config = body["generationConfig"]
        del config["responseJsonSchema"]
        config["responseSchema"] = openapi
        response = _post(
            url,
            model=request.model,
            rpm=_rpm(request.role),
            json=body,
            headers=headers,
            timeout=settings.llm_timeout_seconds,
        )
    if response.status_code >= 400:
        raise ExtractionFailed(_http_error(response, key))
    payload = response.json()
    usage = payload.get("usageMetadata") or {}
    tokens_in = int(usage.get("promptTokenCount", 0))
    # Thinking is billed as output, so it counts toward the cost.
    tokens_out = int(usage.get("candidatesTokenCount", 0)) + int(
        usage.get("thoughtsTokenCount", 0)
    )
    candidates = payload.get("candidates") or [{}]
    content = candidates[0].get("content") or {}
    text = "".join(
        str(part.get("text", ""))
        for part in content.get("parts") or []
        if not part.get("thought")
    )
    reason = candidates[0].get("finishReason")
    try:
        return json.loads(text), tokens_in, tokens_out
    except ValueError:
        # Paid for even though unusable, so the tokens still go into the cost figure.
        raise NoStructuredOutput(
            f"no JSON answer (finish reason {reason})", tokens_in, tokens_out
        ) from None


# Keywords the older `responseSchema` (an OpenAPI subset) accepts.
_OPENAPI_KEYWORDS = {
    "type",
    "format",
    "description",
    "nullable",
    "enum",
    "items",
    "minItems",
    "maxItems",
    "properties",
    "required",
    "minProperties",
    "maxProperties",
    "minLength",
    "maxLength",
    "pattern",
    "minimum",
    "maximum",
    "anyOf",
    "propertyOrdering",
}


def _openapi_schema(schema: dict[str, Any]) -> tuple[dict[str, Any], set[str]]:
    """The schema in the OpenAPI subset: `X | None` becomes nullable X, a constant an
    enum of one, and any other keyword the subset lacks is dropped and named."""
    stripped: set[str] = set()

    def convert(node: Any) -> Any:
        if isinstance(node, list):
            return [convert(item) for item in node]
        if not isinstance(node, dict):
            return node
        options = node.get("anyOf")
        if isinstance(options, list) and {"type": "null"} in options:
            rest = [o for o in options if o != {"type": "null"}]
            merged = {k: v for k, v in node.items() if k != "anyOf"}
            if len(rest) == 1:
                return convert({**merged, **rest[0], "nullable": True})
            return convert({**merged, "anyOf": rest, "nullable": True})
        out: dict[str, Any] = {}
        for key, value in node.items():
            if key == "const":
                out["enum"] = [value]
            elif key == "properties":
                out[key] = {name: convert(sub) for name, sub in value.items()}
            elif key in _OPENAPI_KEYWORDS:
                out[key] = convert(value)
            else:
                stripped.add(key)
        return out

    return convert(schema), stripped


class RateLimiter:
    """Spaces HTTP attempts to each model evenly, across threads: at least 60/limit
    seconds apart, plus a margin. A rolling window let five quick retries go in
    seconds, and the API then counted the next one, a minute after the first, as the
    sixth in its minute.

    The pacing lives in this process only, so only one process may make model calls
    during a run: a second process would keep its own pace and could double the rate.
    """

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._next: dict[str, float] = {}

    def acquire(self, model: str, limit: int, margin: float = 0.0) -> None:
        """Return at this attempt's slot for `model`; 0 means no limit."""
        if limit <= 0:
            return
        with self._lock:
            now = self._clock()
            # Each caller reserves the next free slot, so threads queue up in turn.
            slot = max(now, self._next.get(model, now))
            self._next[model] = slot + 60.0 / limit + margin
        wait = slot - now
        if wait > 0:
            log.info("Model rate limit: waiting %.0fs for %s", wait, model)
            self._sleep(wait)


_LIMITER = RateLimiter()


def _rpm(role: Role) -> int:
    settings = get_settings()
    return settings.extract_rpm if role == "extract" else settings.merge_rpm


def _post(url: str, *, model: str = "", rpm: int = 0, **kwargs: Any) -> httpx.Response:
    """POST, retrying rate limits, overload, and dropped connections with backoff.

    Every attempt, the first and each retry, passes the per-model limiter first.
    """
    settings = get_settings()
    attempts = settings.llm_max_attempts
    for attempt in range(attempts):
        last = attempt + 1 == attempts
        _LIMITER.acquire(model, rpm, settings.llm_rate_margin_seconds)
        try:
            response = httpx.post(url, **kwargs)
        except httpx.TransportError:
            if last:
                raise
            time.sleep(min(2**attempt, 30))
            continue
        if response.status_code not in RETRY_STATUSES or last:
            return response
        asked = _retry_wait(response)
        cap = settings.llm_max_retry_wait_seconds
        if asked is not None and asked > cap:
            # A daily quota asks for hours; waiting would stall the whole run. The
            # failure is cached, and retry-failed asks again later.
            log.info(
                "Model API %s asked to wait %.0fs, over the %.0fs allowed; failing",
                response.status_code,
                asked,
                cap,
            )
            raise RetryWaitTooLong(
                f"HTTP {response.status_code}: the API asked to wait {asked:.0f}s, "
                f"more than the {cap:.0f}s allowed{_quota_note(response)}"
            )
        wait = asked or min(2**attempt, 30)
        log.info("Model API %s; retrying in %.0fs", response.status_code, wait)
        time.sleep(wait)
    raise AssertionError("unreachable")


_SECONDS = re.compile(r"^(\d+(?:\.\d+)?)s$")


class RetryWaitTooLong(ExtractionFailed):
    """The API asked for a longer wait than `llm_max_retry_wait_seconds`."""


def _http_error(response: httpx.Response, secret: str | None = None) -> str:
    """An error response as stored: status, the start of the body, any quota hit."""
    message = f"HTTP {response.status_code}: {response.text[:300]}"
    message += _quota_note(response)
    return message.replace(secret, "[key]") if secret else message


def _quota_note(response: httpx.Response) -> str:
    """Google's QuotaFailure ids, which say whether a per-minute or a per-day quota
    ran out. They hold no secret and no case text."""
    try:
        details = response.json().get("error", {}).get("details") or []
    except (ValueError, AttributeError):
        return ""
    ids = [
        str(violation["quotaId"])
        for detail in details
        if isinstance(detail, dict)
        for violation in detail.get("violations") or []
        if isinstance(violation, dict) and violation.get("quotaId")
    ]
    return f"; quota {', '.join(dict.fromkeys(ids))}" if ids else ""


def _retry_wait(response: httpx.Response) -> float | None:
    """The wait the API asks for: a Retry-After header, or Google's RetryInfo."""
    header = response.headers.get("retry-after", "").strip()
    if header.isdigit():
        return float(header)
    try:
        details = response.json().get("error", {}).get("details") or []
    except ValueError:
        return None
    for detail in details:
        if isinstance(detail, dict):
            match = _SECONDS.match(str(detail.get("retryDelay", "")))
            if match:
                return float(match.group(1))
    return None


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
