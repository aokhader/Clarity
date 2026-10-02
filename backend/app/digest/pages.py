"""Stage 2: split documents into pages with a text layer and a rendered image.

Every PDF page is rendered, because scans need the image for extraction and every page
needs one for the source drawer. A page with almost no text is treated as a scan.
"""

import hashlib
import logging
import re
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import pymupdf
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Page, Source, SourceType

log = logging.getLogger(__name__)

RENDER_DPI = 150
# Fewer characters than this and the page is handled as a scan.
MIN_TEXT_CHARS = 50
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}
TEXT_SUFFIXES = {".txt", ".md", ".csv"}


def build_pages(session: Session, matter_id: int) -> Counter[str]:
    counts: Counter[str] = Counter()
    documents = session.scalars(
        select(Source).where(
            Source.matter_id == matter_id, Source.clio_type == SourceType.DOCUMENT
        )
    ).all()
    for document in documents:
        if not document.file_path or not document.content_hash:
            counts["no_file"] += 1
            continue
        try:
            counts[_build_document_pages(session, document)] += 1
        except (pymupdf.FileDataError, OSError, ValueError) as error:
            log.warning("Could not read document source %s: %s", document.id, error)
            counts["unreadable"] += 1
        session.commit()
    log.info("Pages: %s", dict(counts))
    return counts


def _build_document_pages(session: Session, document: Source) -> str:
    path = Path(str(document.file_path))
    suffix = path.suffix.lower()
    if suffix == ".pdf" or _looks_like_pdf(path):
        return _pdf_pages(session, document, path)
    if suffix in IMAGE_SUFFIXES:
        image = path.read_bytes()
        _upsert_page(session, document, 1, None, str(path), _sha(image))
        return "image"
    if suffix == ".docx":
        _upsert_page(session, document, 1, _docx_text(path), None, None)
        return "docx"
    if suffix in TEXT_SUFFIXES:
        _upsert_page(session, document, 1, path.read_text(errors="ignore"), None, None)
        return "text"
    return "unsupported"


def _pdf_pages(session: Session, document: Source, path: Path) -> str:
    pages_dir = get_settings().pages_dir
    pages_dir.mkdir(parents=True, exist_ok=True)
    # The document hash is in the image name, so an unchanged file is not re-rendered.
    prefix = f"{document.id}_{str(document.content_hash)[:16]}"
    with pymupdf.open(path) as pdf:
        for index, pdf_page in enumerate(pdf, start=1):
            image_path = pages_dir / f"{prefix}_p{index}.png"
            text = pdf_page.get_text().strip()
            if not image_path.exists():
                pdf_page.get_pixmap(dpi=RENDER_DPI).save(image_path)
            has_text = len(text) >= MIN_TEXT_CHARS
            content = text.encode() if has_text else image_path.read_bytes()
            _upsert_page(
                session,
                document,
                index,
                text if has_text else None,
                str(image_path),
                _sha(content),
                has_text_layer=has_text,
            )
        page_count = pdf.page_count
    # Drop pages beyond the current length if the document got shorter.
    for stale in session.scalars(
        select(Page).where(Page.source_id == document.id, Page.page_no > page_count)
    ):
        session.delete(stale)
    return "pdf"


def _upsert_page(
    session: Session,
    document: Source,
    page_no: int,
    text: str | None,
    image_path: str | None,
    content_hash: str | None,
    has_text_layer: bool | None = None,
) -> None:
    content_hash = content_hash or _sha((text or "").encode())
    page = session.scalars(
        select(Page).where(Page.source_id == document.id, Page.page_no == page_no)
    ).first()
    if page is None:
        page = Page(source_id=document.id, page_no=page_no, content_hash=content_hash)
        session.add(page)
    elif page.content_hash != content_hash:
        # Changed content: extraction must run again for this page.
        page.extracted_at = None
    page.content_hash = content_hash
    page.text = text
    page.image_path = image_path
    page.has_text_layer = bool(text) if has_text_layer is None else has_text_layer
    session.flush()


def mark_extracted(page: Page) -> None:
    page.extracted_at = datetime.now(UTC)


def _docx_text(path: Path) -> str:
    """Text of a .docx without a new dependency: paragraphs from word/document.xml."""
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml").decode("utf-8", errors="ignore")
    xml = re.sub(r"</w:p>", "\n", xml)
    return re.sub(r"<[^>]+>", "", xml).strip()


def _looks_like_pdf(path: Path) -> bool:
    with path.open("rb") as handle:
        return handle.read(5) == b"%PDF-"


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
