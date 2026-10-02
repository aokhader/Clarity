"""Text extraction for downloaded case documents.

PDFs keep "[page N]" markers so facts can cite page numbers.
A PDF whose text layer is (nearly) empty is flagged needs_ocr = True for the OCR step.
"""
from pathlib import Path

MIN_CHARS_PER_PAGE = 40


def extract_text(path: Path, content_type: str | None = None) -> dict:
    suffix = path.suffix.lower()
    ctype = (content_type or "").lower()
    try:
        if suffix == ".pdf" or "pdf" in ctype:
            return _pdf(path)
        if suffix == ".docx" or "wordprocessingml" in ctype:
            return _docx(path)
        if suffix in {".txt", ".md", ".csv", ".eml"} or ctype.startswith("text/"):
            text = path.read_text(errors="ignore")
            return _result(text, 1)
        if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff"} or ctype.startswith("image/"):
            return {"text": "", "page_count": 1, "text_chars": 0, "needs_ocr": True, "error": None}
        return {"text": "", "page_count": None, "text_chars": 0, "needs_ocr": False,
                "error": f"unsupported type {suffix or ctype}"}
    except Exception as exc:  # a broken file must not stop ingest
        return {"text": "", "page_count": None, "text_chars": 0, "needs_ocr": False, "error": str(exc)[:300]}


def _pdf(path: Path) -> dict:
    import pdfplumber

    pages = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            pages.append(f"[page {i}]\n{(page.extract_text() or '').strip()}")
        page_count = len(pdf.pages)
    text = "\n\n".join(pages)
    body_chars = sum(len(p.split("\n", 1)[1]) if "\n" in p else 0 for p in pages)
    result = _result(text, page_count, body_chars)
    result["needs_ocr"] = page_count > 0 and body_chars < MIN_CHARS_PER_PAGE * page_count
    return result


def _docx(path: Path) -> dict:
    import docx

    d = docx.Document(str(path))
    text = "\n".join(p.text for p in d.paragraphs if p.text.strip())
    return _result(text, None)


def _result(text: str, page_count, chars=None) -> dict:
    return {"text": text, "page_count": page_count, "text_chars": chars if chars is not None else len(text),
            "needs_ocr": False, "error": None}
