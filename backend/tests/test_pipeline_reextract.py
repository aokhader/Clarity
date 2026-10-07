"""Re-reading chosen pages and records, and nothing else.

Extraction skips what it has read before, so a reworded prompt never reaches existing
facts. The re-extract command marks the chosen pages and records unread; the next
digest reads only those again.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.cli import main
from app.config import get_settings
from app.digest import llm
from app.digest.records import mark_processed
from app.digest.reextract import mark_unread, select_units
from app.digest.run import run_digest
from app.models import Confidence, Fact, FactKind, Origin, Page, Source, SourceType

MATTER = 30
PAGE_TEXT = "Invented page text"
NOTE_TEXT = "Invented note text"


@pytest.fixture
def matter(session: Session) -> dict[str, Any]:
    document = Source(
        matter_id=MATTER, clio_type=SourceType.DOCUMENT, clio_id="d", raw_json={}
    )
    read = datetime(2020, 1, 1, tzinfo=UTC)
    document.pages = [
        Page(
            page_no=n,
            has_text_layer=True,
            text=PAGE_TEXT,
            content_hash=f"p{n}",
            extracted_at=read,
        )
        for n in (1, 2)
    ]
    note = Source(
        matter_id=MATTER,
        clio_type=SourceType.NOTE,
        clio_id="n",
        raw_json={"id": 1, "subject": "Invented", "detail": NOTE_TEXT},
    )
    session.add_all([document, note])
    session.flush()
    mark_processed(note)

    def fact(source: Source, kind: FactKind, page_no: int | None) -> Fact:
        row = Fact(
            matter_id=MATTER,
            kind=kind,
            title="Invented",
            value_json={},
            source_id=source.id,
            page_no=page_no,
            quote="Invented",
            confidence=Confidence.HIGH,
            origin=Origin.MODEL,
            significance=50,
        )
        session.add(row)
        return row

    facts = {
        "visit": fact(document, FactKind.TREATMENT_VISIT, 1),
        "limit": fact(document, FactKind.POLICY_LIMIT, 2),
        "value": fact(note, FactKind.CASE_VALUE, None),
    }
    session.commit()
    return {"document": document, "note": note, **facts}


def test_units_are_chosen_by_page_record_fact_or_kind(
    data_dir: Path, session: Session, matter: dict[str, Any]
) -> None:
    document, note = matter["document"], matter["note"]

    by_kind = select_units(session, MATTER, kinds=["policy_limit"])
    by_fact = select_units(session, MATTER, fact_ids=[matter["value"].id])
    by_name = select_units(session, MATTER, pages=[(document.id, 1)], records=[note.id])

    assert [(p.source_id, p.page_no) for p in by_kind.pages] == [(document.id, 2)]
    assert by_kind.records == []
    assert by_fact.pages == [] and by_fact.records == [note]
    assert [p.page_no for p in by_name.pages] == [1] and by_name.records == [note]


def test_the_next_digest_reads_only_the_chosen_units(
    data_dir: Path,
    session: Session,
    matter: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("EXTRACT_MODEL", "MERGE_MODEL"):
        monkeypatch.setenv(name, "invented")
    get_settings.cache_clear()
    read: list[tuple[str, int | None]] = []

    def model(request: llm.ModelRequest) -> llm.ModelResult:
        if request.purpose.startswith("extract"):
            read.append((request.purpose, request.page_no))
            return llm.ModelResult({"document_type": "other", "facts": []}, 1, 1)
        return llm.ModelResult(None, 0, 0, "not needed here")

    monkeypatch.setattr(llm, "_execute", model)

    mark_unread(select_units(session, MATTER, kinds=["policy_limit", "case_value"]))
    session.commit()
    run_digest(session, MATTER)

    assert sorted(read, key=str) == [("extract_page", 2), ("extract_record", None)]


def test_a_dry_run_changes_nothing(
    data_dir: Path,
    session: Session,
    matter: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        [
            "reextract",
            "--matter-id",
            str(MATTER),
            "--behind-kind",
            "policy_limit",
            "--dry-run",
        ]
    )

    assert code == 0
    assert "1 page" in capsys.readouterr().out
    session.expire_all()
    assert all(p.extracted_at is not None for p in matter["document"].pages)
