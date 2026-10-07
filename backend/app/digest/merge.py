"""Stage 5: merge. Works on stored facts only, never on raw pages, so it cannot introduce
a claim without a source.

1. Deduplicate facts that say the same thing about the same date and provider.
2. Score significance (0 to 100) and who each task is waiting on.
3. Cross-check the firm's own figures against the file (`cross_check.py`).
4. Write the brief, where every sentence cites fact ids that exist.
"""

import hashlib
import json
import logging
from collections import Counter, defaultdict
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.digest import llm
from app.digest.cross_check import cross_check
from app.models import Confidence, Digest, DigestKind, Fact, FactKind, Origin
from app.schemas import BriefContent
from app.services.bills import billed_total_cents

log = logging.getLogger(__name__)

SCORE_BATCH = 50
BRIEF_FACT_LIMIT = 40
# 0 means "not scored yet", so a scored fact is stored with at least 1.
MIN_SCORED = 1
DEDUP_KINDS = {
    FactKind.INJURY,
    FactKind.DIAGNOSIS,
    FactKind.TREATMENT_VISIT,
    FactKind.MEDICAL_BILL,
    FactKind.LIEN,
    FactKind.POLICY_LIMIT,
    FactKind.RECORDS_RECEIVED,
    FactKind.DEADLINE,
}
CONFIDENCE_RANK = {Confidence.HIGH: 0, Confidence.MEDIUM: 1, Confidence.LOW: 2}
WaitingOn = Literal["firm", "client", "provider", "insurer", "court", "other"]
Stage = Literal[
    "intake",
    "treating",
    "treatment_complete",
    "demand",
    "negotiation",
    "litigation",
    "settled",
    "closed",
]


class Score(BaseModel):
    fact_id: int
    significance: int = Field(ge=0, le=100)
    waiting_on: WaitingOn | None = None


class Scores(BaseModel):
    scores: list[Score]


class BriefSentence(BaseModel):
    text: str
    fact_ids: list[int]


class Brief(BaseModel):
    headline: str
    stage: Stage
    stage_fact_ids: list[int]
    sentences: list[BriefSentence]
    open_questions: list[str] = []


def merge(session: Session, matter_id: int) -> Counter[str]:
    counts: Counter[str] = Counter()
    counts["deduplicated"] = deduplicate(session, matter_id)
    counts["scored"] = score(session, matter_id)
    counts["cross_check_disagreements"] = cross_check(session, matter_id)
    counts["brief"] = int(write_brief(session, matter_id))
    session.commit()
    log.info("Merge: %s", dict(counts))
    return counts


def deduplicate(session: Session, matter_id: int) -> int:
    """Keep the best-supported fact per (kind, date, provider, value); link the rest."""
    groups: dict[tuple[Any, ...], list[Fact]] = defaultdict(list)
    for fact in _facts(session, matter_id):
        if (
            fact.kind not in DEDUP_KINDS
            or fact.event_date is None
            or fact.origin is not Origin.MODEL
        ):
            continue
        value = fact.value_json or {}
        # Without a known provider, equal amounts on one date in two documents may be
        # two real charges (same-day copays at two clinics), so only facts from the
        # same source are merged.
        who = (
            ("provider", fact.provider_contact_id)
            if fact.provider_contact_id is not None
            else ("source", fact.source_id)
        )
        key = (
            fact.kind,
            fact.event_date,
            who,
            value.get("amount_cents"),
            str(value.get("body_part") or "").lower(),
        )
        groups[key].append(fact)
    removed = 0
    for group in groups.values():
        if len(group) < 2:
            continue
        group.sort(key=lambda f: (CONFIDENCE_RANK[f.confidence], not f.verified, f.id))
        keeper, duplicates = group[0], group[1:]
        corroborating = sorted({d.source_id for d in duplicates} - {keeper.source_id})
        if corroborating:
            keeper.value_json = {
                **keeper.value_json,
                "corroborating_source_ids": corroborating,
            }
        for duplicate in duplicates:
            session.delete(duplicate)
            removed += 1
    session.flush()
    return removed


def score(session: Session, matter_id: int) -> int:
    unscored = [f for f in _facts(session, matter_id) if f.significance == 0]
    requests = []
    batches = [
        unscored[i : i + SCORE_BATCH] for i in range(0, len(unscored), SCORE_BATCH)
    ]
    for batch in batches:
        rows = [
            {
                "fact_id": f.id,
                "kind": f.kind.value,
                "title": f.title,
                "date": f.event_date.isoformat() if f.event_date else None,
                "quote": (f.quote or "")[:240],
            }
            for f in batch
        ]
        requests.append(
            llm.ModelRequest(
                purpose="significance",
                role="merge",
                prompt=llm.load_prompt("significance"),
                user_text=json.dumps({"facts": rows}, indent=1),
                output=Scores,
                matter_id=matter_id,
            )
        )
    scored = 0
    for batch, result in zip(batches, llm.run_batch(session, requests), strict=True):
        if not isinstance(result, Scores):
            continue
        by_id = {s.fact_id: s for s in result.scores}
        for fact in batch:
            entry = by_id.get(fact.id)
            if entry is None:
                continue
            fact.significance = max(entry.significance, MIN_SCORED)
            if fact.kind is FactKind.TASK and entry.waiting_on:
                fact.value_json = {**fact.value_json, "waiting_on": entry.waiting_on}
            scored += 1
    session.flush()
    return scored


def key_figures(session: Session, matter_id: int) -> dict[str, Any]:
    """Totals the brief may cite as context. The KPI tiles compute their own."""
    facts = _facts(session, matter_id)

    def total(kind: FactKind) -> int:
        return sum(
            (f.value_json or {}).get("amount_cents") or 0
            for f in facts
            if f.kind is kind
        )

    return {
        "medical_bills_total_cents": billed_total_cents(facts),
        "firm_spend_cents": total(FactKind.EXPENSE),
        "medical_specials_fact_ids": [
            f.id for f in facts if f.kind is FactKind.MEDICAL_SPECIALS
        ],
        "policy_limit_fact_ids": [
            f.id for f in facts if f.kind is FactKind.POLICY_LIMIT
        ],
    }


def write_brief(session: Session, matter_id: int) -> bool:
    facts = _facts(session, matter_id)
    if not facts:
        return False
    top = sorted(facts, key=lambda f: (-f.significance, f.id))[:BRIEF_FACT_LIMIT]
    stage_facts = [
        f for f in facts if f.kind in (FactKind.CASE_STAGE, FactKind.STATUS_CHANGE)
    ]
    open_tasks = [
        f
        for f in facts
        if f.kind is FactKind.TASK and f.value_json.get("status") != "complete"
    ]
    included = {f.id: f for f in top + stage_facts + open_tasks}
    figures = key_figures(session, matter_id)
    payload = {
        "facts": [_brief_row(f) for f in included.values()],
        "key_figures": figures,
        "open_task_ids": [f.id for f in open_tasks],
    }
    user_text = json.dumps(payload, indent=1, default=str)
    input_hash = hashlib.sha256(user_text.encode()).hexdigest()
    existing = session.scalars(
        select(Digest).where(
            Digest.matter_id == matter_id, Digest.kind == DigestKind.BRIEF
        )
    ).first()
    if existing is not None and existing.input_hash == input_hash:
        return False
    request = llm.ModelRequest(
        purpose="brief",
        role="merge",
        prompt=llm.load_prompt("brief"),
        user_text=user_text,
        output=Brief,
        matter_id=matter_id,
    )
    result = llm.call(session, request)
    if not isinstance(result, Brief):
        return False
    cited = _cite_only_known(result, set(included))
    content = BriefContent.model_validate(cited.model_dump()).model_dump(mode="json")
    if existing is None:
        existing = Digest(
            matter_id=matter_id,
            kind=DigestKind.BRIEF,
            content_json=content,
            input_hash=input_hash,
            model=request.model,
        )
        session.add(existing)
    existing.content_json = content
    existing.input_hash = input_hash
    existing.model = request.model
    return True


def _cite_only_known(brief: Brief, known_ids: set[int]) -> Brief:
    """Drop any sentence that cites no real fact; a citation is the sentence's license."""
    sentences = []
    for sentence in brief.sentences:
        ids = [i for i in sentence.fact_ids if i in known_ids]
        if ids:
            sentences.append(BriefSentence(text=sentence.text, fact_ids=ids))
    return brief.model_copy(
        update={
            "sentences": sentences,
            "stage_fact_ids": [i for i in brief.stage_fact_ids if i in known_ids],
        }
    )


def _brief_row(fact: Fact) -> dict[str, Any]:
    value = {
        k: v
        for k, v in (fact.value_json or {}).items()
        if k not in ("corroborating_source_ids", "alt_values")
    }
    return {
        "fact_id": fact.id,
        "kind": fact.kind.value,
        "title": fact.title,
        "date": fact.event_date.isoformat() if fact.event_date else None,
        "significance": fact.significance,
        "confidence": fact.confidence.value,
        "value": value,
        "quote": (fact.quote or "")[:200],
    }


def _facts(session: Session, matter_id: int) -> list[Fact]:
    return list(
        session.scalars(
            select(Fact).where(Fact.matter_id == matter_id).order_by(Fact.id)
        )
    )
