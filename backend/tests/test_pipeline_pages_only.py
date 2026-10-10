"""`cli digest --pages-only` renders documents into pages and calls no model.

It lets a newly downloaded document show in the source drawer before anyone pays for
its extraction.
"""

from pathlib import Path

import pymupdf
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.cli import main
from app.config import get_settings
from app.digest import llm
from app.models import DigestRun, LlmCall, Page, Source, SourceType

MATTER = 50
LINE = "Invented filing text, long enough to count as a text layer on its page."


def _pdf(path: Path, pages: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with pymupdf.open() as pdf:
        for n in range(pages):
            pdf.new_page().insert_text((72, 72), f"{LINE} Page {n + 1}.")
        pdf.save(path)


def test_pages_only_renders_every_page_and_calls_no_model(
    data_dir: Path, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EXTRACT_MODEL", "invented-extract")
    monkeypatch.setenv("MERGE_MODEL", "invented-merge")
    get_settings.cache_clear()

    def no_model(_request: llm.ModelRequest) -> llm.ModelResult:
        raise AssertionError("pages-only must not reach a model")

    monkeypatch.setattr(llm, "_execute", no_model)
    _pdf(data_dir / "files" / "70.pdf", pages=2)
    session.add(
        Source(
            matter_id=MATTER,
            clio_type=SourceType.DOCUMENT,
            clio_id="70",
            raw_json={"id": 70, "name": "Invented filing"},
            file_path="files/70.pdf",
            content_hash="invented-hash",
        )
    )
    session.commit()

    assert main(["digest", "--matter-id", str(MATTER), "--pages-only"]) == 0

    session.expire_all()
    pages = session.scalars(select(Page).order_by(Page.page_no)).all()
    assert [p.page_no for p in pages] == [1, 2]
    assert all(p.has_text_layer and p.extracted_at is None for p in pages)
    assert all((data_dir / str(p.image_path)).exists() for p in pages)
    assert session.scalar(select(func.count(LlmCall.id))) == 0
    # Not a digest: the status keeps showing the last real digest.
    assert session.scalar(select(func.count(DigestRun.id))) == 0
