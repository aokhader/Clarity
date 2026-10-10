"""The stored brief, with every citation checked before it reaches the screen.

Each sentence's amounts and dates are also checked against today's file
(`brief_check.py`, D12), so a brief written before a correction says so."""

import logging

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Digest, DigestKind, Fact
from app.schemas import BriefContent, BriefOut, BriefSentenceOut
from app.services.brief_check import check_sentence, file_values
from app.services.fact_views import fact_ref, renderable_facts

log = logging.getLogger(__name__)


class BriefNotFound(LookupError):
    pass


def matter_brief(session: Session, matter_id: int) -> BriefOut:
    digest = session.scalars(
        select(Digest)
        .where(Digest.matter_id == matter_id, Digest.kind == DigestKind.BRIEF)
        .order_by(Digest.created_at.desc(), Digest.id.desc())
    ).first()
    if digest is None:
        raise BriefNotFound(f"matter {matter_id} has no brief yet")
    try:
        content = BriefContent.model_validate(digest.content_json)
    except ValidationError as error:
        # Field paths only: the error's own text quotes the stored brief (case text).
        fields = sorted({".".join(map(str, e["loc"])) for e in error.errors()})
        log.warning(
            "brief %s does not match BriefContent at %s", digest.id, ", ".join(fields)
        )
        raise BriefNotFound(
            f"the stored brief for matter {matter_id} is invalid"
        ) from error

    # Every fact the page may show: the citations, and what the figures are checked against.
    facts: dict[int, Fact] = {
        f.id: f for f in session.scalars(renderable_facts(matter_id))
    }
    file = file_values(list(facts.values()))
    headline_cited = [facts[i] for i in content.headline_fact_ids if i in facts]
    headline_verdict, headline_mentions = check_sentence(
        content.headline, headline_cited, file
    )
    # A sentence is shown only if every fact it cites can be shown; otherwise part of
    # what it says would be on screen without a source.
    sentences = []
    for sentence in content.sentences:
        if not all(i in facts for i in sentence.fact_ids):
            continue
        cited = [facts[i] for i in sentence.fact_ids]
        verdict, mentions = check_sentence(sentence.text, cited, file)
        sentences.append(
            BriefSentenceOut(
                text=sentence.text,
                facts=[fact_ref(f) for f in cited],
                verdict=verdict,
                mentions=mentions,
            )
        )
    return BriefOut(
        headline=content.headline,
        headline_facts=[fact_ref(f) for f in headline_cited],
        headline_verdict=headline_verdict,
        headline_mentions=headline_mentions,
        stage=content.stage,
        stage_facts=[fact_ref(facts[i]) for i in content.stage_fact_ids if i in facts],
        sentences=sentences,
        open_questions=content.open_questions,
        generated_at=digest.created_at,
    )
