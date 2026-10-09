"""Court events are litigation events, and a status change is a move between stages
(D41).

The reads of court filings used to be stored as `other`, or as a `status_change` with
no stage whose free-text label could reach a provider. Only the model API is faked
(`llm._execute`); parsing, quote checks, payloads and storage are the real path.
"""

from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, get_args

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.digest import llm
from app.digest.brief import brief_payload
from app.digest.extract import ExtractedFact, Extraction, Unit, _to_facts
from app.digest.merge import deduplicate
from app.digest.payloads import litigation_event_type
from app.digest.records import visibility_for
from app.digest.run import run_digest
from app.digest.verify import sane_date
from app.models import (
    Confidence,
    Fact,
    FactKind,
    Origin,
    Page,
    Source,
    SourceType,
    Visibility,
)
from app.schemas import LitigationEventType

MATTER = 41
EXTRACTION_PROMPTS = ("extract_page", "extract_record")
FILING_LINE = "The verified complaint in this action was filed on March 4, 2021."
PAGE_TEXT = (
    f"INVENTED COUNTY COURT\nInvented Plaintiff v. Invented Defendant\n{FILING_LINE}"
)


def _prompt_line(prompt: str, kind: str) -> str:
    [line] = [
        line
        for line in llm.load_prompt(prompt).text.splitlines()
        if line.startswith(f"- {kind}:")
    ]
    return line


@pytest.mark.parametrize("prompt", EXTRACTION_PROMPTS)
def test_the_prompts_define_litigation_events_with_every_event_type(
    prompt: str,
) -> None:
    line = _prompt_line(prompt, "litigation_event")
    for event in get_args(LitigationEventType):
        assert event in line, event


@pytest.mark.parametrize("prompt", EXTRACTION_PROMPTS)
def test_the_prompts_keep_court_events_out_of_status_changes(prompt: str) -> None:
    line = _prompt_line(prompt, "status_change")
    assert "to_stage is required" in line
    assert "never a status_change" in line


@pytest.fixture
def filing_page(session: Session) -> Source:
    document = Source(
        matter_id=MATTER,
        clio_type=SourceType.DOCUMENT,
        clio_id="pleading",
        raw_json={"name": "Invented pleading"},
    )
    document.pages = [
        Page(page_no=1, has_text_layer=True, text=PAGE_TEXT, content_hash="p1")
    ]
    session.add(document)
    session.commit()
    return document


def test_a_page_describing_a_filing_is_stored_as_an_internal_litigation_event(
    data_dir: Path,
    session: Session,
    filing_page: Source,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("EXTRACT_MODEL", "MERGE_MODEL"):
        monkeypatch.setenv(name, "invented")
    get_settings.cache_clear()
    # What the model's tool call returns for the page, as raw JSON.
    answer = {
        "document_type": "legal_filing",
        "facts": [
            {
                "kind": "litigation_event",
                "title": "Complaint filed",
                "event_date": "2021-03-04",
                "quote": FILING_LINE,
                "mentions_strategy": False,
                "detail": {"event": "filed", "description": "The verified complaint"},
            }
        ],
    }

    def model(request: llm.ModelRequest) -> llm.ModelResult:
        if request.purpose == "extract_page":
            return llm.ModelResult(answer, 1, 1)
        return llm.ModelResult(None, 0, 0, "not needed here")

    monkeypatch.setattr(llm, "_execute", model)

    run_digest(session, MATTER)

    [fact] = session.scalars(select(Fact).where(Fact.source_id == filing_page.id))
    assert fact.kind is FactKind.LITIGATION_EVENT
    assert fact.value_json["event"] == "filed"
    assert fact.value_json["detail"] == "The verified complaint"
    assert fact.event_date == date(2021, 3, 4)
    assert fact.page_no == 1 and fact.verified
    assert fact.visibility is Visibility.INTERNAL


def _unit(text: str | None) -> Unit:
    return Unit(
        source=Source(
            matter_id=MATTER, clio_type=SourceType.DOCUMENT, clio_id="d", raw_json={}
        ),
        text=text,
        request=llm.ModelRequest(
            purpose="extract_page",
            role="extract",
            prompt=llm.load_prompt("extract_page"),
            user_text=text or "scan",
            output=Extraction,
        ),
    )


def _read(
    kind: str,
    detail: dict[str, Any],
    *,
    text: str | None = FILING_LINE,
    event_date: str | None = None,
) -> tuple[list[Fact], Counter[str], list[Any]]:
    extraction = Extraction(
        document_type="legal_filing",
        facts=[
            ExtractedFact(
                kind=kind,
                title="Invented title",
                quote=FILING_LINE,
                event_date=event_date,
                detail=detail,
            )
        ],
    )
    counts: Counter[str] = Counter()
    second_reads: list[Any] = []
    facts = _to_facts(_unit(text), extraction, {}, counts, second_reads)
    return facts, counts, second_reads


def test_a_status_change_with_no_stage_is_kept_as_other_and_counted() -> None:
    [fact], counts, _ = _read("status_change", {"label": "Invented court event"})

    assert fact.kind is FactKind.OTHER
    assert fact.value_json["detail"] == "Invented court event"
    assert counts["status_change_without_stage"] == 1
    assert visibility_for(fact.kind, fact.mentions_strategy) is Visibility.INTERNAL


def test_a_move_to_a_stage_stays_a_status_change() -> None:
    [fact], counts, _ = _read(
        "status_change", {"to_stage": "litigation", "label": "Moved to litigation"}
    )

    assert fact.kind is FactKind.STATUS_CHANGE
    assert fact.value_json["to_stage"] == "litigation"
    assert counts["status_change_without_stage"] == 0


def test_a_stage_outside_the_list_is_no_stage() -> None:
    [fact], _, _ = _read("status_change", {"to_stage": "pending", "label": "Pending"})

    assert fact.kind is FactKind.OTHER


@pytest.mark.parametrize(
    ("written", "event"),
    [
        ("filed", "filed"),
        ("Complaint filing", "filed"),
        ("action commenced", "filed"),
        ("Answer", "answered"),
        ("dismissal", "dismissed"),
        ("action recommenced", "renewed"),
        ("examination before trial", "deposition"),
        ("decision", "order"),
        ("something else", "other"),
        (None, "other"),
    ],
)
def test_event_words_are_matched_to_the_contracts_types(
    written: str | None, event: str
) -> None:
    assert litigation_event_type(written) == event


def test_an_event_outside_the_list_keeps_the_fact() -> None:
    [fact], _, _ = _read("litigation_event", {"event": "notice of appearance"})

    assert fact.kind is FactKind.LITIGATION_EVENT
    assert fact.value_json["event"] == "other"


def test_a_dated_litigation_event_on_a_scan_gets_a_second_read() -> None:
    [fact], _, second_reads = _read(
        "litigation_event", {"event": "filed"}, text=None, event_date="2021-03-04"
    )

    assert fact.confidence is Confidence.MEDIUM
    assert [pending[0] for pending in second_reads] == [fact]


def test_a_litigation_event_cannot_be_dated_in_the_future() -> None:
    tomorrow = datetime.now(UTC).date() + timedelta(days=1)
    assert sane_date(FactKind.LITIGATION_EVENT, tomorrow) is None


def _event(
    session: Session, source: Source, page_no: int, event: str, significance: int = 0
) -> Fact:
    fact = Fact(
        matter_id=MATTER,
        kind=FactKind.LITIGATION_EVENT,
        title="Invented event",
        value_json={"event": event},
        event_date=date(2021, 3, 4),
        source_id=source.id,
        page_no=page_no,
        quote="Invented quote",
        confidence=Confidence.HIGH,
        origin=Origin.MODEL,
        significance=significance,
    )
    session.add(fact)
    session.flush()
    return fact


def test_a_filing_stamp_read_on_every_page_is_one_event(
    session: Session, filing_page: Source
) -> None:
    for page_no in (1, 2, 3):
        _event(session, filing_page, page_no, "filed")
    served = _event(session, filing_page, 1, "served")

    assert deduplicate(session, MATTER) == 2
    left = session.scalars(select(Fact).where(Fact.matter_id == MATTER)).all()
    assert sorted(f.value_json["event"] for f in left) == ["filed", "served"]
    assert served in left


def test_the_brief_sees_litigation_events_whatever_their_score(
    data_dir: Path,
    session: Session,
    filing_page: Source,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRIEF_FACT_LIMIT", "1")
    get_settings.cache_clear()
    other = Fact(
        matter_id=MATTER,
        kind=FactKind.OTHER,
        title="Invented fact",
        value_json={},
        source_id=filing_page.id,
        page_no=1,
        quote="Invented quote",
        confidence=Confidence.HIGH,
        origin=Origin.MODEL,
        significance=90,
    )
    session.add(other)
    event = _event(session, filing_page, 1, "filed", significance=5)

    ids = {row["fact_id"] for row in brief_payload(session, MATTER)["facts"]}

    assert ids == {other.id, event.id}
