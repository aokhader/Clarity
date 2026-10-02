"""Turn raw Clio records into one unified `events` shape.

Each normalizer returns a dict matching the `events` table. The event id
"<source_type>:<clio_id>" is the provenance key every AI fact points back to.
"""
import html
import json
import re

from .db import now_iso

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+")


def clean_text(value) -> str:
    """Strip HTML (email bodies) and collapse whitespace."""
    if not value:
        return ""
    text = str(value)
    if "<" in text and ">" in text:
        text = re.sub(r"(?i)<br\s*/?>|</p>|</div>", "\n", text)
        text = _TAG_RE.sub("", text)
    text = html.unescape(text)
    text = _WS_RE.sub(" ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def name_of(obj) -> str | None:
    if not obj:
        return None
    if isinstance(obj, list):
        names = [name_of(o) for o in obj]
        return ", ".join(n for n in names if n) or None
    if isinstance(obj, dict):
        return obj.get("name") or obj.get("display_name") or obj.get("email") or (
            str(obj["id"]) if obj.get("id") is not None else None)
    return str(obj)


def first(*values):
    for v in values:
        if v not in (None, "", []):
            return v
    return None


def _event(matter_id, source_type, rec, *, kind=None, date=None, author=None,
           title=None, text=None, extra=None) -> dict:
    return {
        "id": f"{source_type}:{rec['id']}",
        "matter_id": str(matter_id),
        "source_type": source_type,
        "source_id": str(rec["id"]),
        "kind": kind,
        "date": date,
        "author": author,
        "title": (title or "").strip()[:300] or None,
        "text": text or "",
        "extra": json.dumps({k: v for k, v in (extra or {}).items() if v not in (None, "", [])}),
        "updated_at": rec.get("updated_at"),
        "synced_at": now_iso(),
    }


def note(matter_id, rec):
    return _event(matter_id, "note", rec, kind="note",
                  date=first(rec.get("date"), rec.get("created_at")),
                  author=name_of(rec.get("author")),
                  title=rec.get("subject") or "Note",
                  text=clean_text(rec.get("detail")))


def communication(matter_id, rec):
    ctype = (rec.get("type") or "").lower()
    kind = "email" if "email" in ctype else "phone_call" if "phone" in ctype else (ctype or "communication")
    return _event(matter_id, "communication", rec, kind=kind,
                  date=first(rec.get("date"), rec.get("received_at"), rec.get("created_at")),
                  author=first(name_of(rec.get("senders")), name_of(rec.get("user"))),
                  title=rec.get("subject") or kind.replace("_", " ").title(),
                  text=clean_text(rec.get("body")),
                  extra={"senders": name_of(rec.get("senders")),
                         "receivers": name_of(rec.get("receivers"))})


def task(matter_id, rec):
    status = rec.get("status")
    return _event(matter_id, "task", rec, kind="task",
                  date=first(rec.get("due_at"), rec.get("created_at")),
                  author=name_of(rec.get("assigner")),
                  title=rec.get("name") or "Task",
                  text=clean_text(rec.get("description")),
                  extra={"status": status, "priority": rec.get("priority"),
                         "due_at": rec.get("due_at"), "completed_at": rec.get("completed_at"),
                         "assignee": name_of(rec.get("assignee"))})


def calendar_entry(matter_id, rec):
    return _event(matter_id, "calendar_entry", rec, kind="calendar",
                  date=first(rec.get("start_at"), rec.get("created_at")),
                  author=name_of(rec.get("calendar_owner")),
                  title=rec.get("summary") or "Calendar entry",
                  text=clean_text(rec.get("description")),
                  extra={"start_at": rec.get("start_at"), "end_at": rec.get("end_at"),
                         "all_day": rec.get("all_day"), "location": rec.get("location")})


def activity(matter_id, rec):
    atype = (rec.get("type") or "").lower()
    kind = "expense" if "expense" in atype else "time_entry" if "time" in atype else (atype or "activity")
    label = first(name_of(rec.get("expense_category")), name_of(rec.get("activity_description")),
                  kind.replace("_", " ").title())
    return _event(matter_id, "activity", rec, kind=kind,
                  date=first(rec.get("date"), rec.get("created_at")),
                  author=name_of(rec.get("user")),
                  title=label,
                  text=clean_text(rec.get("note")),
                  extra={"total": rec.get("total"), "price": rec.get("price"),
                         "quantity": rec.get("quantity"), "billed": rec.get("billed")})


def document(matter_id, rec, extracted_text: str = "", needs_ocr: bool = False, page_count=None):
    return _event(matter_id, "document", rec, kind="document",
                  date=first(rec.get("received_at"), rec.get("created_at")),
                  author=name_of(rec.get("creator")),
                  title=rec.get("name") or "Document",
                  text=extracted_text[:6000],  # full text lives in documents.text
                  extra={"category": name_of(rec.get("document_category")),
                         "folder": name_of(rec.get("parent")),
                         "content_type": rec.get("content_type"),
                         "needs_ocr": needs_ocr, "page_count": page_count})


def custom_field(matter_id, rec):
    name = first(rec.get("field_name"), name_of(rec.get("custom_field")), f"Custom field {rec['id']}")
    return _event(matter_id, "custom_field", rec, kind=rec.get("field_type") or "custom_field",
                  date=first(rec.get("updated_at"), rec.get("created_at")),
                  title=name,
                  text=custom_field_value(rec))


def custom_field_value(rec) -> str:
    option = rec.get("picklist_option")
    if isinstance(option, dict) and option.get("option"):
        return str(option["option"])
    value = rec.get("value")
    if isinstance(value, dict):
        return name_of(value) or json.dumps(value)
    return "" if value is None else str(value)


NORMALIZERS = {
    "note": note,
    "communication": communication,
    "task": task,
    "calendar_entry": calendar_entry,
    "activity": activity,
}
