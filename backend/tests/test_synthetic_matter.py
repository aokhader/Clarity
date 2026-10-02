"""The seed must cover what docs/parallel.md promises tracks B and C."""

import json
import re
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Confidence,
    Digest,
    DigestKind,
    Fact,
    FactKind,
    Page,
    Source,
    SourceType,
    Visibility,
)
from app.schemas import BriefContent, validate_payload
from tests.fixtures.synthetic_matter import MATTER_ID, load_synthetic_matter


def _facts(session: Session) -> list[Fact]:
    return list(session.scalars(select(Fact).where(Fact.matter_id == MATTER_ID)))


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def test_every_fact_kind_appears(seeded: Session) -> None:
    assert {fact.kind for fact in _facts(seeded)} == set(FactKind)


def test_every_payload_matches_its_kind(seeded: Session) -> None:
    for fact in _facts(seeded):
        assert validate_payload(fact.kind, fact.value_json) == fact.value_json


def test_every_quote_is_in_its_source(seeded: Session) -> None:
    pages = {(p.source_id, p.page_no): p for p in seeded.scalars(select(Page))}
    for fact in _facts(seeded):
        assert fact.quote, f"fact {fact.id} has no quote"
        if fact.source.clio_type is SourceType.DOCUMENT:
            page = pages[(fact.source_id, fact.page_no)]
            if page.text is None:
                continue  # a scan: nothing to match, which is why these are not high confidence
            haystack = page.text
        else:
            haystack = json.dumps(fact.source.raw_json, ensure_ascii=False)
        assert _normalize(fact.quote) in _normalize(haystack), fact.title


def test_document_has_a_text_page_and_a_scanned_page(
    seeded: Session, data_dir: Path
) -> None:
    pages = list(seeded.scalars(select(Page).order_by(Page.page_no)))
    assert [page.has_text_layer for page in pages] == [True, False]
    for page in pages:
        assert page.image_path and (data_dir / page.image_path).is_file()
    document = seeded.scalars(
        select(Source).where(Source.clio_type == SourceType.DOCUMENT)
    ).one()
    assert document.file_path and (data_dir / document.file_path).is_file()


def test_covers_two_providers_both_visibilities_and_disagreement(
    seeded: Session,
) -> None:
    facts = _facts(seeded)
    billing_providers = {
        f.provider_contact_id for f in facts if f.kind is FactKind.MEDICAL_BILL
    }
    assert len(billing_providers) == 2
    assert {f.visibility for f in facts} == set(Visibility)
    assert any(f.confidence is Confidence.LOW for f in facts)
    assert any(f.value_json["alt_values"] for f in facts)
    source_types = {f.source.clio_type for f in facts}
    assert {
        SourceType.NOTE,
        SourceType.COMMUNICATION,
        SourceType.DOCUMENT,
    } <= source_types


def test_brief_cites_only_existing_facts(seeded: Session) -> None:
    stored = seeded.scalars(select(Digest).where(Digest.kind == DigestKind.BRIEF)).one()
    brief = BriefContent.model_validate(stored.content_json)
    fact_ids = {fact.id for fact in _facts(seeded)}
    for sentence in brief.sentences:
        assert set(sentence.fact_ids) <= fact_ids
    assert set(brief.stage_fact_ids) <= fact_ids


def test_reseeding_replaces_instead_of_duplicating(seeded: Session) -> None:
    counts = [
        seeded.scalar(select(func.count()).select_from(m)) for m in (Source, Fact, Page)
    ]
    load_synthetic_matter(seeded)
    seeded.commit()
    assert [
        seeded.scalar(select(func.count()).select_from(m)) for m in (Source, Fact, Page)
    ] == counts
