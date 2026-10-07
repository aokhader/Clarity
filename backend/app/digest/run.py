"""`cli digest`: structured -> pages -> mapping -> extract -> merge, each stage idempotent.

Mapping runs before extraction (the design doc lists it under merge) because the
extractor needs the list of medical providers to attribute facts. A second run with
no changes makes zero model calls: every request is answered from the cache.
"""

import logging
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.digest.extract import extract_all
from app.digest.llm import ModelsNotConfigured
from app.digest.mapping import build_mapping
from app.digest.merge import merge
from app.digest.pages import build_pages
from app.digest.structured import build_structured_facts
from app.models import DigestRun, LlmCall, Source

log = logging.getLogger(__name__)


class NoSyncedMatter(Exception):
    pass


def synced_matter_id(session: Session, matter_id: int | None = None) -> int:
    if matter_id is not None:
        return matter_id
    ids = list(session.scalars(select(Source.matter_id).distinct()))
    if not ids:
        raise NoSyncedMatter("Nothing synced yet. Run: python -m app.cli sync")
    if len(ids) > 1:
        raise NoSyncedMatter(f"Several matters synced {ids}; pass --matter-id")
    return int(ids[0])


def run_digest(session: Session, matter_id: int) -> DigestRun:
    run = DigestRun(matter_id=matter_id)
    session.add(run)
    session.commit()
    first_call_id = session.scalar(select(func.max(LlmCall.id))) or 0
    stats: dict[str, Any] = {}
    errors: list[str] = []
    try:
        stats["structured"] = dict(build_structured_facts(session, matter_id))
        stats["pages"] = dict(build_pages(session, matter_id))
        mapping = build_mapping(session, matter_id)
        # The previous mapping stood in for a failed call; the run says so.
        errors.extend(mapping.errors)
        stats["extract"] = dict(extract_all(session, matter_id, mapping))
        stats["merge"] = dict(merge(session, matter_id))
    except ModelsNotConfigured as error:
        session.rollback()
        errors.append(str(error))
    except Exception as error:
        # Record the failure so the run does not look unfinished forever, then raise.
        session.rollback()
        _finish(session, run, stats, first_call_id, f"{type(error).__name__}: {error}")
        raise
    _finish(session, run, stats, first_call_id, "; ".join(errors) or None)
    log.info("Digest finished: %s", stats["model_calls"])
    return run


def _finish(
    session: Session,
    run: DigestRun,
    stats: dict[str, Any],
    first_call_id: int,
    error: str | None,
) -> None:
    stats["model_calls"] = _call_counts(session, first_call_id)
    run.finished_at = datetime.now(UTC)
    run.stats_json = stats
    run.error = error[:2000] if error else None
    session.commit()


def _call_counts(session: Session, after_id: int) -> dict[str, int]:
    calls = session.scalars(select(LlmCall).where(LlmCall.id > after_id)).all()
    counts: Counter[str] = Counter()
    for call in calls:
        counts["cache_hits" if call.cache_hit else "model_calls"] += 1
        if call.error:
            counts["errors"] += 1
        counts["cost_micro_usd"] += call.cost_micro_usd
    return dict(counts)
