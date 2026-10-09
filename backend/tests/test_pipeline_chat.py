"""Chat (D49): the one model call behind an answer, and the checks code makes on it.

The chat role's request carries its own output limit, effort and refusal fallback,
while the digest's requests stay byte for byte as they were, so the digest cache keeps
answering. An answer the fallback gave is priced at the fallback's rates. Code keeps a
sentence only when every id it cites was in the input, and an uncited sentence only
when it says the file does not answer, without a figure.

Only the model API is faked (`llm._execute`, or `httpx.post` for the wire); the cache
in `llm.py` is real. Every record here is invented.
"""

import json
import logging
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.digest import brief, chat, llm
from app.digest.chat import (
    AttachedItem,
    ChatInput,
    PageExcerpt,
    PriorTurn,
    answer_question,
)
from app.models import Confidence, Fact, FactKind, LlmCall, Origin, Source, SourceType

MATTER = 7
CHAT_MODEL = "invented-chat-model"
MERGE_MODEL = "invented-merge-model"
UNKNOWN_ID = 999_999


def _settings(data_dir: Path, **values: Any) -> Settings:
    """Built without the .env file, so the developer's own settings cannot leak in."""
    base: dict[str, Any] = {
        "data_dir": data_dir,
        "llm_provider": "anthropic",
        "llm_api_key": "test-key",
        "extract_model": "invented-extract-model",
        "merge_model": MERGE_MODEL,
        "extract_price_in": Decimal(1),
        "extract_price_out": Decimal(1),
        "merge_price_in": Decimal(1),
        "merge_price_out": Decimal(1),
        "chat_model": CHAT_MODEL,
        "chat_price_in": Decimal(2),
        "chat_price_out": Decimal(10),
    }
    return Settings(_env_file=None, **(base | values))  # type: ignore[call-arg]


def _use(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    monkeypatch.setattr(llm, "get_settings", lambda: settings)
    monkeypatch.setattr(chat, "get_settings", lambda: settings)


# --- The wire -----------------------------------------------------------------------


class _Out(BaseModel):
    value: int


def _request(role: llm.Role) -> llm.ModelRequest:
    return llm.ModelRequest(
        purpose="test",
        role=role,
        prompt=llm.Prompt(name="test", version="1", text="Return a value."),
        user_text="input",
        output=_Out,
        matter_id=MATTER,
    )


class Wire:
    """The model API: records each body and header set, answers with one tool call."""

    def __init__(self, served_model: str, tokens: tuple[int, int] = (1000, 200)):
        self.served_model = served_model
        self.tokens = tokens
        self.bodies: list[dict[str, Any]] = []
        self.headers: list[dict[str, str]] = []

    def __call__(
        self, url: str, json: dict[str, Any], headers: dict[str, str], **_kw: object
    ) -> httpx.Response:
        self.bodies.append(json)
        self.headers.append(headers)
        return httpx.Response(
            200,
            json={
                "model": self.served_model,
                "stop_reason": "tool_use",
                "content": [
                    {"type": "thinking", "thinking": "Invented reasoning."},
                    {"type": "tool_use", "name": llm.TOOL_NAME, "input": {"value": 1}},
                ],
                "usage": {
                    "input_tokens": self.tokens[0],
                    "output_tokens": self.tokens[1],
                },
            },
        )


def _wire(monkeypatch: pytest.MonkeyPatch, served_model: str) -> Wire:
    wire = Wire(served_model)
    monkeypatch.setattr(llm.httpx, "post", wire)
    return wire


def test_a_chat_request_asks_for_effort_its_own_limit_and_the_fallback(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use(monkeypatch, _settings(data_dir))
    wire = _wire(monkeypatch, CHAT_MODEL)

    result = llm._execute(_request("chat"))

    assert result.data == {"value": 1}
    body, headers = wire.bodies[0], wire.headers[0]
    assert body["model"] == CHAT_MODEL
    assert body["max_tokens"] == 16000
    assert body["output_config"] == {"effort": "medium"}
    assert body["fallbacks"] == "default"
    assert headers["anthropic-beta"] == "server-side-fallback-2026-07-01"
    assert body["tool_choice"] == {"type": "auto"}
    # Adaptive thinking comes from leaving the field out; no prefilled answer either.
    assert "thinking" not in body
    assert [m["role"] for m in body["messages"]] == ["user"]


@pytest.mark.parametrize("role", ["extract", "merge"])
def test_digest_requests_are_byte_for_byte_what_they_were(
    role: llm.Role, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Chat settings that differ from every default, so any leak would show.
    _use(
        monkeypatch,
        _settings(data_dir, chat_effort="max", chat_max_output_tokens=32000),
    )
    model = "invented-extract-model" if role == "extract" else MERGE_MODEL
    wire = _wire(monkeypatch, model)

    llm._execute(_request(role))

    # The body as the digest built it before chat existed, keys in the same order.
    before = {
        "model": model,
        "max_tokens": 4096,
        "system": f"Return a value.\n\n{llm.TOOL_INSTRUCTION}",
        "messages": [{"role": "user", "content": [{"type": "text", "text": "input"}]}],
        "tools": [
            {
                "name": llm.TOOL_NAME,
                "description": "Record the result.",
                "input_schema": llm._inline_refs(_Out.model_json_schema()),
            }
        ],
        "tool_choice": {"type": "auto"},
    }
    assert json.dumps(wire.bodies[0]) == json.dumps(before)
    assert wire.headers[0] == {
        "x-api-key": "test-key",
        "anthropic-version": llm.ANTHROPIC_VERSION,
    }


@pytest.mark.parametrize(
    ("served", "recorded", "cost"),
    [
        # 1,000 in at $2 and 200 out at $10 a million: 2,000 + 2,000 micro-dollars.
        (CHAT_MODEL, CHAT_MODEL, 4000),
        # A dated snapshot of the chat model is the chat model.
        (f"{CHAT_MODEL}-20310101", CHAT_MODEL, 4000),
        # The fallback answered: $5 and $25 a million, 5,000 + 5,000.
        ("invented-fallback-model", "invented-fallback-model", 10000),
    ],
)
def test_a_chat_call_is_priced_at_the_rates_of_the_model_that_answered(
    served: str,
    recorded: str,
    cost: int,
    session: Session,
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use(monkeypatch, _settings(data_dir))
    _wire(monkeypatch, served)

    llm.call(session, _request("chat"))

    row = session.scalars(select(LlmCall)).one()
    assert (row.input_tokens, row.output_tokens) == (1000, 200)
    assert row.cost_micro_usd == cost
    assert row.model == recorded


def test_a_digest_call_has_no_fallback_whatever_model_the_response_names(
    session: Session, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use(monkeypatch, _settings(data_dir))
    _wire(monkeypatch, "invented-other-model")

    llm.call(session, _request("merge"))

    row = session.scalars(select(LlmCall)).one()
    assert (row.model, row.cost_micro_usd) == (MERGE_MODEL, 1200)


def test_chat_on_the_merge_model_shares_its_pace(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    on_merge = _settings(data_dir, chat_model=MERGE_MODEL, merge_rpm=50)
    _use(monkeypatch, on_merge)
    assert llm.role_settings("chat").rpm == 50
    # Both set: the stricter holds, since the limiter's slots are keyed by model name.
    _use(
        monkeypatch,
        _settings(data_dir, chat_model=MERGE_MODEL, merge_rpm=50, chat_rpm=10),
    )
    assert llm.role_settings("chat").rpm == 10
    # Another model, and no CHAT_RPM: no pacing of chat's own.
    _use(monkeypatch, _settings(data_dir, merge_rpm=50))
    assert llm.role_settings("chat").rpm == 0


# --- The answer ---------------------------------------------------------------------


def _source(session: Session) -> Source:
    source = Source(
        matter_id=MATTER,
        clio_type=SourceType.DOCUMENT,
        clio_id="1",
        raw_json={"name": "Invented clinic record"},
    )
    session.add(source)
    session.flush()
    return source


def _fact(session: Session, source: Source, kind: FactKind, **values: Any) -> Fact:
    fields: dict[str, Any] = {
        "title": "Invented fact",
        "value_json": {},
        "quote": "Invented quote",
        "confidence": Confidence.HIGH,
        "origin": Origin.MODEL,
        "significance": 60,
        "page_no": 1,
    }
    fact = Fact(matter_id=MATTER, kind=kind, source_id=source.id, **(fields | values))
    session.add(fact)
    session.flush()
    return fact


class Facts:
    def __init__(self, session: Session) -> None:
        source = _source(session)
        self.source = source
        self.visit = _fact(session, source, FactKind.TREATMENT_VISIT)
        self.diagnosis = _fact(session, source, FactKind.DIAGNOSIS, page_no=2)
        # In no section of the input; citable only through the firm-spend key figure.
        self.expense = _fact(
            session, source, FactKind.EXPENSE, value_json={"amount_cents": 4200}
        )
        session.commit()


def _input(facts: Facts) -> ChatInput:
    return ChatInput(
        overview=[facts.visit],
        brief_sentences=[("Invented brief sentence.", [facts.visit.id])],
        attached=[
            AttachedItem(
                label="Visit",
                facts=[facts.visit],
                pages=[PageExcerpt(facts.source.id, 1, "Invented page text.", [])],
            )
        ],
        retrieved=[facts.visit, facts.diagnosis],
        pages=[
            PageExcerpt(facts.source.id, 2, "More invented text.", [facts.diagnosis.id])
        ],
        history=[PriorTurn("An earlier invented question?", "An earlier answer.")],
    )


def _sentence(text: str, ids: list[int], not_in_file: bool = False) -> dict[str, Any]:
    return {"text": text, "fact_ids": ids, "not_in_file": not_in_file}


class FakeModel:
    def __init__(self, answer: dict[str, Any] | None) -> None:
        self.answer = answer
        self.requests: list[llm.ModelRequest] = []

    def __call__(self, request: llm.ModelRequest) -> llm.ModelResult:
        self.requests.append(request)
        if self.answer is None:
            return llm.ModelResult(
                None, 1, 0, "ExtractionFailed: HTTP 529: invented body with record text"
            )
        return llm.ModelResult(self.answer, 100, 20)


@pytest.fixture
def facts(session: Session, data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Facts:
    _use(monkeypatch, _settings(data_dir))
    return Facts(session)


def _model(monkeypatch: pytest.MonkeyPatch, answer: dict[str, Any] | None) -> FakeModel:
    fake = FakeModel(answer)
    monkeypatch.setattr(llm, "_execute", fake)
    return fake


def _ask(session: Session, facts: Facts, question: str = "What happened?") -> Any:
    return answer_question(
        session, matter_id=MATTER, question=question, chat_input=_input(facts)
    )


def test_the_model_sees_the_pointed_at_items_first_and_the_question_last(
    facts: Facts, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _model(monkeypatch, {"sentences": [], "no_answer": True})

    _ask(session, facts)

    request = fake.requests[0]
    assert (request.purpose, request.role) == ("chat", "chat")
    assert request.prompt.name == "chat_answer"
    sent = json.loads(request.user_text)
    keys = list(sent)
    assert keys[0] == "pointed_at" and keys[-1] == "question"
    assert keys.index("earlier_turns") == len(keys) - 2
    item = sent["pointed_at"][0]
    assert item["label"] == "Visit"
    assert [row["fact_id"] for row in item["facts"]] == [facts.visit.id]
    assert item["pages"][0]["source"] == "Invented clinic record, page 1"
    # Shown once: the pointed-at visit is not repeated in the later sections.
    assert sent["overview"] == []
    assert [row["fact_id"] for row in sent["facts"]] == [facts.diagnosis.id]
    assert sent["pages"][0]["fact_ids"] == [facts.diagnosis.id]
    assert sent["key_figures"]["firm_spend_total"]["fact_ids"] == [facts.expense.id]


def test_code_keeps_only_cited_sentences_and_a_figure_free_not_in_file(
    facts: Facts, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _model(
        monkeypatch,
        {
            "sentences": [
                _sentence("The client had a visit.", [facts.visit.id]),
                _sentence("The firm has spent money.", [facts.expense.id]),
                _sentence("The page names a diagnosis.", [facts.diagnosis.id]),
                _sentence("The file does not say when care ends.", [], True),
                # One id the model was not shown drops the whole sentence.
                _sentence("The visit was paid.", [facts.visit.id, UNKNOWN_ID]),
                # Uncited, and not a not-in-file sentence.
                _sentence("The client is recovering well.", []),
                # Not in the file, yet stating an amount or a date.
                _sentence("The file does not show the $500 payment.", [], True),
                _sentence("Nothing is recorded after Mar 3, 2031.", [], True),
            ],
            "no_answer": False,
        },
    )

    answer = _ask(session, facts)

    assert [(s.text, s.fact_ids, s.not_in_file) for s in answer.sentences] == [
        ("The client had a visit.", [facts.visit.id], False),
        ("The firm has spent money.", [facts.expense.id], False),
        ("The page names a diagnosis.", [facts.diagnosis.id], False),
        ("The file does not say when care ends.", [], True),
    ]
    assert answer.dropped == 4
    assert answer.error is None and answer.no_answer is False
    row = session.get(LlmCall, answer.llm_call_id)
    assert row is not None and row.purpose == "chat" and not row.cache_hit


def test_the_same_question_again_is_answered_from_the_cache(
    facts: Facts, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    answer = {
        "sentences": [_sentence("A visit.", [facts.visit.id])],
        "no_answer": False,
    }
    fake = _model(monkeypatch, answer)

    first = _ask(session, facts)
    second = _ask(session, facts)

    assert len(fake.requests) == 1
    assert second.sentences == first.sentences
    hit = session.get(LlmCall, second.llm_call_id)
    assert hit is not None and hit.cache_hit and hit.cost_micro_usd == 0


def test_a_failed_answer_says_why_without_record_text_and_is_asked_again(
    facts: Facts, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _model(monkeypatch, None)

    first = _ask(session, facts)
    second = _ask(session, facts)

    assert first.sentences == [] and first.error == "The model API answered HTTP 529."
    assert "record text" not in (first.error or "")
    # A cached failure is never replayed: the second question goes to the model.
    assert len(fake.requests) == 2
    assert second.llm_call_id is not None and second.llm_call_id > first.llm_call_id


def test_chat_without_a_model_is_not_configured(
    facts: Facts, session: Session, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _model(monkeypatch, {"sentences": [], "no_answer": True})
    _use(monkeypatch, _settings(data_dir, chat_model=None))

    with pytest.raises(llm.ModelsNotConfigured):
        _ask(session, facts)
    with pytest.raises(llm.ModelsNotConfigured, match="CHAT_MODEL"):
        _ = _request("chat").model
    assert fake.requests == []


def test_chat_is_configured_only_with_a_key_a_model_and_both_prices(
    data_dir: Path,
) -> None:
    assert _settings(data_dir).chat_configured
    assert not _settings(data_dir, chat_price_out=None).chat_configured
    assert not _settings(data_dir, llm_api_key=None).chat_configured
    assert not _settings(data_dir, chat_model=None).chat_configured


def test_the_chat_prompt_is_versioned() -> None:
    assert llm.load_prompt("chat_answer").version == "1"


# --- The input's size (D50) ---------------------------------------------------------


def test_the_input_is_compact_json(
    facts: Facts, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _model(monkeypatch, {"sentences": [], "no_answer": True})

    _ask(session, facts)

    sent = fake.requests[0].user_text
    assert sent == json.dumps(json.loads(sent), separators=(",", ":"))
    assert "\n" not in sent


def test_an_item_shows_only_its_most_significant_facts(
    session: Session, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _settings(data_dir).chat_item_facts == 25
    assert _settings(data_dir).chat_context_facts == 40
    _use(monkeypatch, _settings(data_dir, chat_item_facts=2))
    source = _source(session)
    low = _fact(session, source, FactKind.TREATMENT_VISIT, significance=10)
    high = _fact(session, source, FactKind.TREATMENT_VISIT, significance=90)
    mid = _fact(session, source, FactKind.TREATMENT_VISIT, significance=50)
    tied = _fact(session, source, FactKind.TREATMENT_VISIT, significance=50)
    session.commit()
    chat_input = ChatInput(
        overview=[low, high],
        brief_sentences=[],
        attached=[AttachedItem(label="Visits", facts=[low, high, mid, tied], pages=[])],
        retrieved=[],
        pages=[],
        history=[],
    )
    fake = _model(
        monkeypatch,
        {
            "sentences": [
                _sentence("A visit the overview shows.", [low.id]),
                # Past the item's cap and in no other section, so not citable.
                _sentence("A visit the model was not shown.", [tied.id]),
            ],
            "no_answer": False,
        },
    )

    answer = answer_question(
        session, matter_id=MATTER, question="Which visits?", chat_input=chat_input
    )

    sent = json.loads(fake.requests[0].user_text)
    rows = sent["pointed_at"][0]["facts"]
    # Most significant first; on a tie, the caller's order.
    assert [row["fact_id"] for row in rows] == [high.id, mid.id]
    # A fact past the cap is not hidden from the sections after the items.
    assert [row["fact_id"] for row in sent["overview"]] == [low.id]
    # The order carries the significance; confidence and the quote stay.
    for row in [*rows, *sent["overview"]]:
        assert "significance" not in row
        assert row["confidence"] == "high" and row["quote"] == "Invented quote"
    assert [s.fact_ids for s in answer.sentences] == [[low.id]]
    assert answer.dropped == 1


def test_the_brief_input_is_unchanged_so_its_cache_key_holds(
    session: Session, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use(monkeypatch, _settings(data_dir))
    fact = _fact(session, _source(session), FactKind.TREATMENT_VISIT)
    session.commit()
    sent: list[llm.ModelRequest] = []

    def no_answer(_session: Session, request: llm.ModelRequest) -> None:
        sent.append(request)

    monkeypatch.setattr(llm, "call", no_answer)

    brief.write_brief(session, MATTER)

    # The brief's row and layout as they were before chat: indented, with significance.
    row = {
        "fact_id": fact.id,
        "kind": "treatment_visit",
        "title": "Invented fact",
        "date": None,
        "source": "Invented clinic record, page 1",
        "significance": 60,
        "confidence": "high",
        "value": {},
        "quote": "Invented quote",
    }
    expected = {"facts": [row], "key_figures": {}, "open_task_ids": []}
    assert sent[0].user_text == json.dumps(expected, indent=1)


SECRET = "Invented record text that must never reach a log"


def _tool_call(value: object) -> dict[str, Any]:
    return {"type": "tool_use", "name": llm.TOOL_NAME, "input": {"value": value}}


class ScriptedWire:
    """The model API answering each attempt in turn from a script."""

    def __init__(self, *answers: tuple[str, list[dict[str, Any]]]) -> None:
        self.answers = list(answers)

    def __call__(self, url: str, **_kw: object) -> httpx.Response:
        stop_reason, content = self.answers.pop(0)
        return httpx.Response(
            200,
            json={
                "model": CHAT_MODEL,
                "stop_reason": stop_reason,
                "content": content,
                "usage": {"input_tokens": 1000, "output_tokens": 50},
            },
        )


@pytest.mark.parametrize(
    ("first", "reason"),
    [
        (("end_turn", [{"type": "text", "text": SECRET}]), "no tool call"),
        (("max_tokens", [{"type": "thinking", "thinking": SECRET}]), "max_tokens"),
        (("refusal", [{"type": "text", "text": SECRET}]), "refusal"),
        (("tool_use", [_tool_call(SECRET)]), "schema failure (value int_parsing)"),
    ],
)
def test_a_second_attempt_is_logged_with_its_reason_and_no_record_text(
    first: tuple[str, list[dict[str, Any]]],
    reason: str,
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _use(monkeypatch, _settings(data_dir))
    monkeypatch.setattr(
        llm.httpx, "post", ScriptedWire(first, ("tool_use", [_tool_call(1)]))
    )
    caplog.set_level(logging.INFO, logger=llm.__name__)

    result = llm._execute(_request("chat"))

    assert result.data == {"value": 1}
    # Both attempts are billed.
    assert (result.input_tokens, result.output_tokens) == (2000, 100)
    lines = [m for r in caplog.records if "second attempt" in (m := r.getMessage())]
    assert lines == [
        (
            f"test call (role chat) needs a second attempt: {reason}; the first "
            "billed 1000 tokens in, 50 out"
        )
    ]
    assert SECRET not in caplog.text


def test_a_call_answered_at_once_logs_no_second_attempt(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _use(monkeypatch, _settings(data_dir))
    monkeypatch.setattr(llm.httpx, "post", ScriptedWire(("tool_use", [_tool_call(1)])))
    caplog.set_level(logging.INFO, logger=llm.__name__)

    assert llm._execute(_request("chat")).data == {"value": 1}
    assert "second attempt" not in caplog.text
