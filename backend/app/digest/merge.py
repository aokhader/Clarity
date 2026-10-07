"""Stage 5: merge. Works on stored facts only, never on raw pages, so it cannot introduce
a claim without a source.

1. Deduplicate facts that say the same thing about the same date and provider.
2. Score significance (0 to 100) and who each task is waiting on.
3. Cross-check the firm's own figures against the file (`cross_check.py`).
4. Write the brief, where every sentence cites fact ids that exist (`brief.py`).
"""

import json
import logging
from collections import Counter, defaultdict
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.digest import llm
from app.digest.brief import write_brief
from app.digest.cross_check import cross_check
from app.models import Confidence, Fact, FactKind, Origin

log = logging.getLogger(__name__)

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


class Score(BaseModel):
    fact_id: int
    significance: int = Field(ge=0, le=100)
    waiting_on: WaitingOn | None = None


class Scores(BaseModel):
    scores: list[Score]


def merge(session: Session, matter_id: int) -> Counter[str]:
    counts: Counter[str] = Counter()
    counts["deduplicated"] = deduplicate(session, matter_id)
    counts.update(score(session, matter_id))
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


def score(session: Session, matter_id: int) -> Counter[str]:
    """Score every unscored fact, in batches.

    A fact the model leaves out of a batch it answered is asked about again in a
    smaller batch. Left out twice, it gets the lowest score and is counted, so later
    digests do not ask about it again. A batch whose call failed stays unscored; its
    failure is cached and the run reports it.
    """
    counts: Counter[str] = Counter()
    pending = [f for f in _facts(session, matter_id) if f.significance == 0]
    for _attempt in range(get_settings().score_passes):
        if not pending:
            break
        scored, pending = _score_batches(session, matter_id, pending)
        counts["scored"] += scored
    for fact in pending:
        fact.significance = MIN_SCORED
    counts["score_dropped"] = len(pending)
    session.flush()
    return counts


def _score_batches(
    session: Session, matter_id: int, unscored: list[Fact]
) -> tuple[int, list[Fact]]:
    """Score in batches; return the count and the facts answered batches left out."""
    requests = []
    size = get_settings().score_batch_size
    batches = [unscored[i : i + size] for i in range(0, len(unscored), size)]
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
    left_out: list[Fact] = []
    for batch, result in zip(batches, llm.run_batch(session, requests), strict=True):
        if not isinstance(result, Scores):
            continue
        by_id = {s.fact_id: s for s in result.scores}
        for fact in batch:
            entry = by_id.get(fact.id)
            if entry is None:
                left_out.append(fact)
                continue
            fact.significance = max(entry.significance, MIN_SCORED)
            if fact.kind is FactKind.TASK and entry.waiting_on:
                fact.value_json = {**fact.value_json, "waiting_on": entry.waiting_on}
            scored += 1
    return scored, left_out


def _facts(session: Session, matter_id: int) -> list[Fact]:
    return list(
        session.scalars(
            select(Fact).where(Fact.matter_id == matter_id).order_by(Fact.id)
        )
    )
