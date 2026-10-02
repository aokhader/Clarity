"""Sync worker: pull one matter and everything attached to it into `sources`.

Raw first: every record is stored exactly as Clio returned it, and parsing happens in
the digest. A parsing bug never needs another sync. Records whose ETag is unchanged are
skipped, and documents are downloaded again only when their ETag changes.
"""

import hashlib
import logging
import mimetypes
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clio.client import ClioClient, ClioError
from app.config import get_settings
from app.models import Source, SourceType, SyncRun

log = logging.getLogger(__name__)


# Field lists are tried in order. Clio rejects an unknown field name with a 400, so
# each list falls back to a smaller one rather than failing the whole sync. Confirm
# names against docs/reference/clio-openapi.json when it is available.
def _fields(*parts: str) -> str:
    return ",".join(parts)


MATTER_SEARCH_FIELDS = "id,display_number,description,updated_at"
_CUSTOM_FIELDS = (
    "custom_field_values{id,etag,field_name,field_type,value,created_at,updated_at,"
    "picklist_option{option}}"
)
MATTER_FIELDS = (
    _fields(
        "id,etag,display_number,description,status,open_date,close_date",
        "created_at,updated_at,practice_area{name},matter_stage{name}",
        "client{id,name,type},responsible_attorney{id,name}",
        _CUSTOM_FIELDS,
    ),
    _fields(
        "id,etag,display_number,description,status,open_date,close_date",
        "created_at,updated_at,practice_area{name},client{id,name,type}",
        "custom_field_values{id,field_name,value}",
    ),
    "id,etag,display_number,description,status,created_at,updated_at,client{id,name}",
)
RELATIONSHIP_FIELDS = (
    "id,etag,description,contact{id,name,type},created_at,updated_at",
    "id,description,contact{id,name}",
)
CONTACT_FIELDS = (
    _fields(
        "id,etag,name,type,title,email_addresses{address,name}",
        "phone_numbers{number,name},created_at,updated_at",
    ),
    "id,etag,name,type,created_at,updated_at",
)
NOTE_FIELDS = (
    "id,etag,subject,detail,date,author{id,name},created_at,updated_at",
    "id,etag,subject,detail,date,created_at,updated_at",
)
COMMUNICATION_FIELDS = (
    _fields(
        "id,etag,subject,body,type,date,senders{id,name,type}",
        "receivers{id,name,type},created_at,updated_at",
    ),
    "id,etag,subject,body,type,date,created_at,updated_at",
)
TASK_FIELDS = (
    _fields(
        "id,etag,name,description,status,priority,due_at,completed_at",
        "assignee{id,name,type},created_at,updated_at",
    ),
    "id,etag,name,description,status,priority,due_at,completed_at,created_at,updated_at",
)
CALENDAR_FIELDS = (
    "id,etag,summary,description,location,start_at,end_at,all_day,created_at,updated_at",
)
ACTIVITY_FIELDS = (
    _fields(
        "id,etag,type,date,total,price,quantity,note,expense_category{id,name}",
        "vendor{id,name},created_at,updated_at",
    ),
    _fields(
        "id,etag,type,date,total,price,quantity,note,expense_category{id,name}",
        "created_at,updated_at",
    ),
    "id,etag,type,date,total,note,created_at,updated_at",
)
DOCUMENT_FIELDS = (
    _fields(
        "id,etag,name,content_type,size,created_at,updated_at,parent{id,name}",
        "document_category{id,name},latest_document_version{id,size,content_type}",
    ),
    "id,etag,name,content_type,size,created_at,updated_at",
)

# (source type, path, extra params, field lists)
MATTER_RECORDS: tuple[tuple[SourceType, str, dict[str, str], tuple[str, ...]], ...] = (
    (SourceType.NOTE, "notes.json", {"type": "Matter"}, NOTE_FIELDS),
    (SourceType.COMMUNICATION, "communications.json", {}, COMMUNICATION_FIELDS),
    (SourceType.TASK, "tasks.json", {}, TASK_FIELDS),
    (SourceType.CALENDAR_ENTRY, "calendar_entries.json", {}, CALENDAR_FIELDS),
    (SourceType.ACTIVITY, "activities.json", {}, ACTIVITY_FIELDS),
)

REJECTED_FIELDS_STATUSES = (400, 422)
UNAVAILABLE_STATUSES = (403, 404)


class MatterNotFound(Exception):
    pass


@dataclass
class SyncStats:
    counts: Counter[str] = field(default_factory=Counter)
    errors: list[str] = field(default_factory=list)

    def as_json(self) -> dict[str, Any]:
        return {"counts": dict(self.counts), "errors": self.errors}


def find_matter(client: ClioClient, query: str) -> list[dict[str, Any]]:
    return client.get_all(
        "matters.json", {"query": query, "fields": MATTER_SEARCH_FIELDS}
    )


def resolve_matter_id(
    client: ClioClient, query: str | None, matter_id: int | None
) -> int:
    if matter_id is not None:
        return matter_id
    if not query:
        raise MatterNotFound("Set CLIO_MATTER_QUERY in .env or pass --matter-id")
    matches = find_matter(client, query)
    if not matches:
        raise MatterNotFound(f"No Clio matter matches the configured query ({query!r})")
    if len(matches) > 1:
        log.warning(
            "%d matters match the query; using the most recently updated", len(matches)
        )
    best = max(matches, key=lambda m: str(m.get("updated_at") or ""))
    return int(best["id"])


def sync_matter(session: Session, client: ClioClient, matter_id: int) -> SyncRun:
    run = SyncRun(matter_id=matter_id)
    session.add(run)
    session.commit()
    stats = SyncStats()
    since = _last_successful_sync(session, matter_id)
    try:
        _sync(session, client, matter_id, since, stats)
    except ClioError as error:
        stats.errors.append(str(error))
        run.error = str(error)[:2000]
        log.error("Sync stopped: %s", error)
    run.finished_at = datetime.now(UTC)
    run.stats_json = stats.as_json()
    session.commit()
    log.info(
        "Sync finished: %s, %d errors, %d requests",
        dict(stats.counts),
        len(stats.errors),
        client.request_count,
    )
    return run


def _sync(
    session: Session,
    client: ClioClient,
    matter_id: int,
    since: datetime | None,
    stats: SyncStats,
) -> None:
    matter = _get_with_fallback(client, f"matters/{matter_id}.json", {}, MATTER_FIELDS)
    _upsert(session, matter_id, SourceType.MATTER, matter, stats)
    for value in matter.get("custom_field_values") or []:
        _upsert(session, matter_id, SourceType.CUSTOM_FIELD, value, stats)
    session.commit()

    scope: dict[str, Any] = {"matter_id": matter_id}
    if since is not None:
        scope["updated_since"] = since.isoformat()

    relationships = _list_with_fallback(
        client,
        "relationships.json",
        {"matter_id": matter_id},
        RELATIONSHIP_FIELDS,
        "relationship",
        stats,
    )
    contact_ids = {int(r["contact"]["id"]) for r in relationships if r.get("contact")}
    for relationship in relationships:
        _upsert(session, matter_id, SourceType.RELATIONSHIP, relationship, stats)
    if (matter.get("client") or {}).get("id"):
        contact_ids.add(int(matter["client"]["id"]))
    for contact_id in sorted(contact_ids):
        try:
            contact = _get_with_fallback(
                client, f"contacts/{contact_id}.json", {}, CONTACT_FIELDS
            )
            _upsert(session, matter_id, SourceType.CONTACT, contact, stats)
        except ClioError as error:
            stats.errors.append(f"contact {contact_id}: {error.status}")
    session.commit()

    for source_type, path, extra, fields in MATTER_RECORDS:
        records = _list_with_fallback(
            client, path, {**scope, **extra}, fields, source_type.value, stats
        )
        for record in records:
            _upsert(session, matter_id, source_type, record, stats)
        session.commit()

    documents = _list_with_fallback(
        client, "documents.json", scope, DOCUMENT_FIELDS, "document", stats
    )
    for document in documents:
        changed = _upsert(session, matter_id, SourceType.DOCUMENT, document, stats)
        source = _find(session, matter_id, SourceType.DOCUMENT, str(document["id"]))
        if source is not None and (changed or not _file_present(source)):
            _download(client, source, document, stats)
        session.commit()


def _upsert(
    session: Session,
    matter_id: int,
    source_type: SourceType,
    record: dict[str, Any],
    stats: SyncStats,
) -> bool:
    """Insert or update one record. Returns False when the ETag shows no change."""
    clio_id = str(record["id"])
    etag = record.get("etag")
    source = _find(session, matter_id, source_type, clio_id)
    if source is not None and etag and source.etag == etag:
        stats.counts[f"{source_type.value}_unchanged"] += 1
        return False
    if source is None:
        source = Source(matter_id=matter_id, clio_type=source_type, clio_id=clio_id)
        session.add(source)
        stats.counts[f"{source_type.value}_new"] += 1
    else:
        stats.counts[f"{source_type.value}_updated"] += 1
    source.etag = etag
    source.raw_json = record
    source.clio_created_at = _parse_datetime(record.get("created_at"))
    source.clio_updated_at = _parse_datetime(record.get("updated_at"))
    source.synced_at = datetime.now(UTC)
    if source_type is not SourceType.DOCUMENT:
        # Documents are hashed over the file bytes once downloaded.
        source.content_hash = None
    session.flush()
    return True


def _download(
    client: ClioClient, source: Source, record: dict[str, Any], stats: SyncStats
) -> None:
    files_dir = get_settings().files_dir
    destination = files_dir / f"{source.clio_id}{_extension(record)}"
    try:
        client.download(f"documents/{source.clio_id}/download.json", destination)
    except ClioError as error:
        stats.errors.append(f"document {source.clio_id} download: {error.status}")
        return
    source.file_path = str(destination)
    source.content_hash = hashlib.sha256(destination.read_bytes()).hexdigest()
    stats.counts["document_downloaded"] += 1


def _list_with_fallback(
    client: ClioClient,
    path: str,
    params: dict[str, Any],
    field_sets: tuple[str, ...],
    label: str,
    stats: SyncStats,
) -> list[dict[str, Any]]:
    for index, fields in enumerate(field_sets):
        try:
            records = client.get_all(path, {**params, "fields": fields})
        except ClioError as error:
            if error.status in REJECTED_FIELDS_STATUSES and index + 1 < len(field_sets):
                log.warning(
                    "%s: Clio rejected the field list, trying a smaller one", label
                )
                continue
            if error.status in UNAVAILABLE_STATUSES:
                stats.errors.append(f"{label}: not available ({error.status})")
                return []
            raise
        if index:
            stats.counts[f"{label}_fallback_fields"] = index
        return records
    return []


def _get_with_fallback(
    client: ClioClient, path: str, params: dict[str, Any], field_sets: tuple[str, ...]
) -> dict[str, Any]:
    last_error: ClioError | None = None
    for fields in field_sets:
        try:
            return client.get(path, {**params, "fields": fields})["data"]
        except ClioError as error:
            if error.status not in REJECTED_FIELDS_STATUSES:
                raise
            last_error = error
    assert last_error is not None
    raise last_error


def _find(
    session: Session, matter_id: int, source_type: SourceType, clio_id: str
) -> Source | None:
    return session.scalars(
        select(Source).where(
            Source.matter_id == matter_id,
            Source.clio_type == source_type,
            Source.clio_id == clio_id,
        )
    ).first()


def _last_successful_sync(session: Session, matter_id: int) -> datetime | None:
    run = session.scalars(
        select(SyncRun)
        .where(
            SyncRun.matter_id == matter_id,
            SyncRun.finished_at.is_not(None),
            SyncRun.error.is_(None),
        )
        .order_by(SyncRun.id.desc())
    ).first()
    return run.started_at if run else None


def _file_present(source: Source) -> bool:
    return bool(source.file_path) and Path(str(source.file_path)).exists()


def _extension(record: dict[str, Any]) -> str:
    suffix = Path(str(record.get("name") or "")).suffix.lower()
    if suffix and len(suffix) <= 6:
        return suffix
    guessed = mimetypes.guess_extension(str(record.get("content_type") or ""))
    return guessed or ".bin"


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
