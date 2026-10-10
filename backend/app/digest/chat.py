"""The answer to one question about a matter, from the records the caller gives (D49).

Backend picks the records (`services/chat_context.py`) and stores the turn; this module
makes the one model call and checks its answer in code. Every sentence must cite fact
ids the model was shown. The only uncited sentence kept is one that says the file does
not answer, and it may state no amount or date. Nothing here writes to the database
except the model-call log.
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.digest import llm
from app.digest.brief import fact_row, key_figures, source_label
from app.models import Fact, LlmCall, Source
from app.services.money_mentions import find_amounts
from app.services.text_mentions import find_dates

log = logging.getLogger(__name__)

__all__ = [
    "AttachedItem",
    "ChatAnswer",
    "ChatAnswerSentence",
    "ChatInput",
    "PageExcerpt",
    "PriorTurn",
    "answer_question",
    "chat_row",
    "shown_item_facts",
]


@dataclass
class PageExcerpt:
    source_id: int
    page_no: int | None
    text: str  # already cut to CHAT_PAGE_CHARS by the caller
    fact_ids: list[int]  # renderable facts read from this page; the only ids to cite


@dataclass
class AttachedItem:
    label: str  # AskItemOut.label
    # Renderable facts, restatements included, at most 50; the model is shown the
    # CHAT_ITEM_FACTS most significant (`shown_item_facts`).
    facts: list[Fact]
    pages: list[PageExcerpt]


@dataclass
class PriorTurn:
    question: str
    answer: str  # the shown sentences of a done turn, joined; "" for a failed turn


@dataclass
class ChatInput:
    overview: list[Fact]  # stage, incident, KPI and brief facts
    brief_sentences: list[tuple[str, list[int]]]  # the stored brief's sentences, ids
    attached: list[AttachedItem]
    retrieved: list[Fact]  # ranked for the question, CHAT_CONTEXT_FACTS at most
    pages: list[PageExcerpt]  # for retrieved facts, CHAT_CONTEXT_PAGES at most
    history: list[PriorTurn]  # the thread's last CHAT_HISTORY_TURNS, oldest first


@dataclass
class ChatAnswerSentence:
    text: str
    fact_ids: list[int]  # empty only when not_in_file
    not_in_file: bool


@dataclass
class ChatAnswer:
    sentences: list[ChatAnswerSentence]  # after the code checks
    no_answer: bool
    dropped: int  # sentences the code checks removed
    llm_call_id: int | None  # the llm_calls row for this answer
    error: str | None  # set when the call failed; sentences then empty


class ChatReplySentence(BaseModel):
    text: str
    fact_ids: list[int]
    not_in_file: bool


class ChatReply(BaseModel):
    """What the model returns; `ChatAnswer` is what is left after the code checks."""

    sentences: list[ChatReplySentence]
    no_answer: bool


def answer_question(
    session: Session, *, matter_id: int, question: str, chat_input: ChatInput
) -> ChatAnswer:
    """One model call, then the checks. Raises `llm.ModelsNotConfigured` when chat is
    off; a failed call comes back as an answer with `error` set and no sentences."""
    if not get_settings().chat_configured:
        raise llm.ModelsNotConfigured(
            "Set CHAT_MODEL, CHAT_PRICE_IN and CHAT_PRICE_OUT in .env"
        )
    payload = chat_payload(session, matter_id, question, chat_input)
    request = llm.ModelRequest(
        purpose="chat",
        role="chat",
        prompt=llm.load_prompt("chat_answer"),
        # Compact: indentation is a tenth of the characters and buys the model nothing.
        user_text=json.dumps(payload, separators=(",", ":")),
        output=ChatReply,
        matter_id=matter_id,
    )
    # Failed calls are cached like any other; asking again must ask the model again.
    with llm.retrying_failed_calls():
        reply = llm.call(session, request)
    row = session.scalars(
        select(LlmCall)
        .where(LlmCall.cache_key == request.cache_key)
        .order_by(LlmCall.id.desc())
        .limit(1)
    ).first()
    call_id = row.id if row is not None else None
    if not isinstance(reply, ChatReply):
        log.info("Chat answer failed for matter %s (llm call %s)", matter_id, call_id)
        return ChatAnswer(
            sentences=[],
            no_answer=False,
            dropped=0,
            llm_call_id=call_id,
            error=_short_reason(row.error if row is not None else None),
        )
    sentences, dropped = checked_sentences(reply, citable_ids(payload))
    log.info(
        "Chat answer for matter %s: %d sentences kept, %d dropped (llm call %s)",
        matter_id,
        len(sentences),
        dropped,
        call_id,
    )
    return ChatAnswer(
        sentences=sentences,
        no_answer=reply.no_answer,
        dropped=dropped,
        llm_call_id=call_id,
        error=None,
    )


def chat_payload(
    session: Session, matter_id: int, question: str, chat_input: ChatInput
) -> dict[str, Any]:
    """The model's input, built like the brief's. What the user pointed at comes first;
    a fact or page shown in one section is not repeated in a later one."""
    shown_facts: set[int] = set()
    shown_pages: set[tuple[int, int | None]] = set()

    def rows(facts: list[Fact]) -> list[dict[str, Any]]:
        fresh = [f for f in _unique(facts) if f.id not in shown_facts]
        shown_facts.update(f.id for f in fresh)
        return [chat_row(f) for f in fresh]

    def excerpts(pages: list[PageExcerpt]) -> list[dict[str, Any]]:
        fresh = []
        for page in pages:
            if (page.source_id, page.page_no) not in shown_pages:
                shown_pages.add((page.source_id, page.page_no))
                fresh.append(_excerpt(session, page))
        return fresh

    # Each item lists its facts, even one another item also holds, so every item reads
    # whole; the sections after them leave out what the items showed. A fact an item
    # leaves out past its cap may still come in a later section.
    items = [(item, shown_item_facts(item.facts)) for item in chat_input.attached]
    pointed_at = [
        {
            "label": item.label,
            "facts": [chat_row(f) for f in facts],
            "pages": excerpts(item.pages),
        }
        for item, facts in items
    ]
    shown_facts.update(f.id for _, facts in items for f in facts)
    matter_facts = list(
        session.scalars(
            select(Fact).where(Fact.matter_id == matter_id).order_by(Fact.id)
        )
    )
    return {
        "pointed_at": pointed_at,
        "overview": rows(chat_input.overview),
        "brief": [
            {"text": text, "fact_ids": ids} for text, ids in chat_input.brief_sentences
        ],
        "facts": rows(chat_input.retrieved),
        "key_figures": key_figures(matter_facts),
        "pages": excerpts(chat_input.pages),
        "earlier_turns": [
            {"question": turn.question, "answer": turn.answer}
            for turn in chat_input.history
        ],
        "question": question,
    }


def shown_item_facts(facts: list[Fact]) -> list[Fact]:
    """The pointed-at item's facts the model is shown: its CHAT_ITEM_FACTS most
    significant, most significant first; on a tie, the caller's order holds."""
    ranked = sorted(_unique(facts), key=lambda f: -f.significance)
    return ranked[: get_settings().chat_item_facts]


def chat_row(fact: Fact) -> dict[str, Any]:
    """A fact as the chat model sees it: the brief's row without its significance,
    which the order mostly carries (an item's facts come most significant first, the
    retrieved facts in rank order). `fact_row` stays as it is: the brief's input is
    its cache key."""
    row = fact_row(fact)
    del row["significance"]
    return row


def _unique(facts: list[Fact]) -> list[Fact]:
    return list({f.id: f for f in facts}.values())


def _excerpt(session: Session, page: PageExcerpt) -> dict[str, Any]:
    source = session.get(Source, page.source_id)
    label = source_label(source, page.page_no) if source is not None else "Source"
    return {"source": label, "fact_ids": page.fact_ids, "text": page.text}


def citable_ids(payload: dict[str, Any]) -> set[int]:
    """Every fact id the model was shown, and the ids behind each key figure."""
    ids: set[int] = set()
    pages = list(payload["pages"])
    for item in payload["pointed_at"]:
        ids.update(row["fact_id"] for row in item["facts"])
        pages.extend(item["pages"])
    for section in ("overview", "facts"):
        ids.update(row["fact_id"] for row in payload[section])
    for sentence in payload["brief"]:
        ids.update(sentence["fact_ids"])
    for page in pages:
        ids.update(page["fact_ids"])
    for figure in payload["key_figures"].values():
        ids.update(figure["fact_ids"])
    return ids


def checked_sentences(
    reply: ChatReply, citable: set[int]
) -> tuple[list[ChatAnswerSentence], int]:
    """The sentences that pass, and how many did not. Stricter than the brief's check:
    one id the model was not shown drops the whole sentence, since its text may rest
    on that id."""
    kept: list[ChatAnswerSentence] = []
    for sentence in reply.sentences:
        text = sentence.text.strip()
        ids = list(dict.fromkeys(sentence.fact_ids))
        if not text or any(i not in citable for i in ids):
            continue
        if sentence.not_in_file:
            # It stands on no record, so it may not state a figure.
            if _states_a_figure(text):
                continue
        elif not ids:
            continue
        kept.append(ChatAnswerSentence(text, ids, sentence.not_in_file))
    return kept, len(reply.sentences) - len(kept)


def _states_a_figure(text: str) -> bool:
    """An amount (with a money marker, or a bare number of four digits or more, which
    takes in a year) or a date."""
    return bool(find_amounts(text) or find_dates(text))


_HTTP_STATUS = re.compile(r"\bHTTP (\d{3})\b")


def _short_reason(error: str | None) -> str:
    """Why the call failed, in words safe to show and store: a status or the kind of
    error, never the error's text, which can quote the records or the answer."""
    if not error:
        return "The model call failed."
    if status := _HTTP_STATUS.search(error):
        return f"The model API answered HTTP {status.group(1)}."
    if error.startswith("no valid output"):
        return "The model's answer did not have the expected form."
    kind = error.split(":", 1)[0].strip()
    if kind.isidentifier():
        return f"The model call failed ({kind})."
    return "The model call failed."
