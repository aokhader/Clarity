"""Stage 1: facts from records that are already structured. No model calls.

A task's due date or a calendar entry's start time is exact in Clio, so code maps it.
These facts are `origin = code`, `confidence = high`, `verified = true`.
"""

import logging
from collections import Counter
from typing import Any

from sqlalchemy.orm import Session

from app.digest.payloads import build_payload, contact_channel
from app.digest.records import (
    QUOTE_LIMIT,
    is_processed,
    mark_processed,
    name_of,
    parse_date,
    replace_facts,
    sources_of,
)
from app.models import Confidence, Fact, FactKind, Origin, Source, SourceType

log = logging.getLogger(__name__)


def build_structured_facts(session: Session, matter_id: int) -> Counter[str]:
    counts: Counter[str] = Counter()
    client_id = client_contact_id(session, matter_id)
    builders = {
        SourceType.TASK: _task_facts,
        SourceType.CALENDAR_ENTRY: _calendar_facts,
        SourceType.COMMUNICATION: lambda s: _communication_facts(s, client_id),
    }
    for source_type, builder in builders.items():
        for source in sources_of(session, matter_id, source_type):
            # Communications are also read by the extractor, so they are marked done
            # by extract.py; here they are rebuilt each run, which is cheap.
            if source_type is not SourceType.COMMUNICATION and is_processed(source):
                counts["unchanged"] += 1
                continue
            facts = builder(source)
            replace_facts(session, source, facts, Origin.CODE)
            if source_type is not SourceType.COMMUNICATION:
                mark_processed(source)
            counts[source_type.value] += len(facts)
    session.commit()
    log.info("Structured facts: %s", dict(counts))
    return counts


def client_contact_id(session: Session, matter_id: int) -> int | None:
    matters = sources_of(session, matter_id, SourceType.MATTER)
    if not matters:
        return None
    client = matters[0].raw_json.get("client") or {}
    return int(client["id"]) if client.get("id") else None


def _code_fact(
    kind: FactKind, title: str, quote: str, event_date: Any, payload: dict[str, Any]
) -> Fact:
    return Fact(
        kind=kind,
        title=title[:120],
        quote=quote[:QUOTE_LIMIT],
        event_date=parse_date(event_date),
        value_json=build_payload(kind, None, payload),
        confidence=Confidence.HIGH,
        verified=True,
        significance=0,
        mentions_strategy=False,
    )


def _task_facts(source: Source) -> list[Fact]:
    raw = source.raw_json
    name = str(raw.get("name") or "Task")
    done = bool(raw.get("completed_at")) or str(raw.get("status")).lower() == "complete"
    quote = name if not raw.get("description") else f"{name}: {raw['description']}"
    facts = [
        _code_fact(
            FactKind.TASK,
            name,
            quote,
            raw.get("due_at") or raw.get("created_at"),
            {
                "status": "complete" if done else "open",
                "due_at": raw.get("due_at"),
                "assignee": name_of(raw.get("assignee")),
            },
        )
    ]
    if raw.get("statute_of_limitations") and raw.get("due_at"):
        facts.append(
            _code_fact(
                FactKind.DEADLINE,
                name,
                quote,
                raw.get("due_at"),
                {"deadline_type": "statute_of_limitations", "due_at": raw["due_at"]},
            )
        )
    return facts


def _calendar_facts(source: Source) -> list[Fact]:
    raw = source.raw_json
    summary = str(raw.get("summary") or "Calendar entry")
    quote = summary if not raw.get("location") else f"{summary} ({raw['location']})"
    return [
        _code_fact(
            FactKind.DEADLINE,
            summary,
            quote,
            raw.get("start_at"),
            {"deadline_type": "calendar_entry", "due_at": raw.get("start_at")},
        )
    ]


def _communication_facts(source: Source, client_id: int | None) -> list[Fact]:
    raw = source.raw_json
    if client_id is None:
        return []
    senders = {int(p["id"]) for p in raw.get("senders") or [] if p.get("id")}
    receivers = {int(p["id"]) for p in raw.get("receivers") or [] if p.get("id")}
    if client_id not in senders | receivers:
        return []
    direction = "inbound" if client_id in senders else "outbound"
    channel = contact_channel(str(raw.get("type") or ""))
    subject = str(raw.get("subject") or raw.get("type") or "Communication")
    return [
        _code_fact(
            FactKind.CLIENT_CONTACT,
            f"Client contact: {subject}",
            subject,
            raw.get("date") or raw.get("created_at"),
            {"channel": channel, "direction": direction},
        )
    ]
