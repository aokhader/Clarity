"""Pull one matter from Clio into the local SQLite database.

Usage:
    python -m backend.ingest --list                 # list matters in the account
    python -m backend.ingest                        # ingest the only matter (or prompt if several)
    python -m backend.ingest --query <name>         # ingest the matter matching a search
    python -m backend.ingest --matter-id 123456     # ingest a specific matter
    python -m backend.ingest --incremental          # only records updated since the last sync
    python -m backend.ingest --skip-docs            # skip downloading documents

Clio is only read (GET). Nothing is written back.
"""
import argparse
import json
import re
import sys
from collections import Counter

from . import config, db, normalize
from .clio_client import ClioHTTPError, ClioReadOnlyClient
from .docs_text import extract_text

# Field sets are tried in order: if Clio rejects a field name (400/422), we fall back to a smaller set.
MATTER_FIELDS = [
    "id,etag,display_number,description,status,open_date,close_date,created_at,updated_at,"
    "practice_area{name},client{id,name,type},responsible_attorney{name},"
    "custom_field_values{id,field_name,field_type,value,updated_at,custom_field{id,name},picklist_option{option}}",
    "id,display_number,description,status,open_date,close_date,created_at,updated_at,client{id,name},"
    "custom_field_values{id,field_name,field_type,value}",
    "id,display_number,description,status,client{id,name}",
]

RESOURCES = [
    # (event source_type, endpoint, extra params, field sets)
    ("note", "notes.json", {"type": "Matter"}, [
        "id,subject,detail,date,created_at,updated_at,author{name}",
        "id,subject,detail,date,created_at,updated_at",
    ]),
    ("communication", "communications.json", {}, [
        "id,subject,body,type,date,received_at,created_at,updated_at,senders{name},receivers{name},user{name}",
        "id,subject,body,type,date,created_at,updated_at,user{name}",
        "id,subject,body,type,date,created_at,updated_at",
    ]),
    ("task", "tasks.json", {}, [
        "id,name,description,status,priority,due_at,completed_at,created_at,updated_at,assignee{name},assigner{name}",
        "id,name,description,status,priority,due_at,completed_at,created_at,updated_at",
    ]),
    ("calendar_entry", "calendar_entries.json", {}, [
        "id,summary,description,location,start_at,end_at,all_day,created_at,updated_at,calendar_owner{name}",
        "id,summary,description,location,start_at,end_at,all_day,created_at,updated_at",
    ]),
    ("activity", "activities.json", {}, [
        "id,type,date,quantity,price,total,note,billed,created_at,updated_at,user{name},"
        "activity_description{name},expense_category{name}",
        "id,type,date,quantity,price,total,note,created_at,updated_at",
    ]),
]

RELATIONSHIP_FIELDS = [
    "id,description,contact{id,name,type,primary_email_address,primary_phone_number}",
    "id,description,contact{id,name,type}",
]

DOCUMENT_FIELDS = [
    "id,name,content_type,size,created_at,updated_at,received_at,parent{name},document_category{name},creator{name}",
    "id,name,content_type,created_at,updated_at,parent{name}",
    "id,name,created_at,updated_at",
]


def fetch_with_fallback(client: ClioReadOnlyClient, path: str, params: dict, field_sets: list[str],
                        label: str) -> list[dict]:
    for i, fields in enumerate(field_sets):
        try:
            records = client.get_all(path, {**params, "fields": fields})
            if i > 0:
                print(f"  {label}: used fallback field set #{i}")
            return records
        except ClioHTTPError as exc:
            if exc.status in (400, 422):
                print(f"  {label}: Clio rejected fields ({exc.body[:160].strip()}), trying smaller set")
                continue
            if exc.status in (403, 404):
                print(f"  {label}: not available ({exc.status}), skipping")
                return []
            raise
    print(f"  {label}: every field set was rejected, skipping")
    return []


def get_matter(client, matter_id: str) -> dict:
    for fields in MATTER_FIELDS:
        try:
            return client.get(f"matters/{matter_id}.json", {"fields": fields})["data"]
        except ClioHTTPError as exc:
            if exc.status in (400, 422):
                continue
            raise
    raise SystemExit(f"Could not read matter {matter_id}")


def list_matters(client, query: str | None = None) -> list[dict]:
    params = {"fields": "id,display_number,description,status,client{name}"}
    if query:
        params["query"] = query
    return client.get_all("matters.json", params)


def resolve_matter_id(client, args) -> str:
    if args.matter_id:
        return str(args.matter_id)
    if config.CLIO_MATTER_ID and not args.query:
        return config.CLIO_MATTER_ID
    matters = list_matters(client, args.query)
    if not matters:
        raise SystemExit("No matters found" + (f" for query '{args.query}'" if args.query else ""))
    if len(matters) == 1:
        return str(matters[0]["id"])
    print("Several matters found; re-run with --matter-id:")
    print_matters(matters)
    raise SystemExit(1)


def print_matters(matters):
    for m in matters:
        client_name = (m.get("client") or {}).get("name", "")
        print(f"  {m['id']:>12}  {m.get('display_number', ''):<20} {m.get('status', ''):<8} {client_name}")


def safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name or "file")[:120]


def ingest(client: ClioReadOnlyClient, conn, matter_id: str, incremental=False, skip_docs=False) -> Counter:
    counts = Counter()
    since = db.last_sync_time(conn, matter_id) if incremental else None
    run = conn.execute("INSERT INTO sync_runs (matter_id, mode, started_at) VALUES (?,?,?)",
                       (matter_id, "incremental" if since else "full", db.now_iso()))
    run_id = run.lastrowid
    conn.commit()
    base_params = {"matter_id": matter_id}
    if since:
        base_params["updated_since"] = since
        print(f"Incremental sync: records updated since {since}")

    # 1. Matter + custom fields
    matter = get_matter(client, matter_id)
    db.save_raw(conn, "matter", matter, matter_id)
    client_obj = matter.get("client") or {}
    db.upsert(conn, "matters", {
        "id": str(matter["id"]),
        "display_number": matter.get("display_number"),
        "description": matter.get("description"),
        "status": matter.get("status"),
        "practice_area": normalize.name_of(matter.get("practice_area")),
        "open_date": matter.get("open_date"),
        "close_date": matter.get("close_date"),
        "client_id": str(client_obj["id"]) if client_obj.get("id") else None,
        "client_name": client_obj.get("name"),
        "responsible_attorney": normalize.name_of(matter.get("responsible_attorney")),
        "created_at": matter.get("created_at"),
        "updated_at": matter.get("updated_at"),
        "synced_at": db.now_iso(),
    }, ("id",))
    for cf in matter.get("custom_field_values") or []:
        event = normalize.custom_field(matter_id, cf)
        db.upsert(conn, "custom_fields", {
            "id": str(cf["id"]), "matter_id": matter_id, "name": event["title"],
            "field_type": cf.get("field_type"), "value": event["text"],
        }, ("id", "matter_id"))
        db.upsert(conn, "events", event, ("id",))
        counts["custom_field"] += 1
    print(f"Matter {matter.get('display_number')} — {matter.get('description', '')}")

    # 2. Contacts and their roles on this matter
    if client_obj.get("id"):
        db.upsert(conn, "contacts", {
            "id": str(client_obj["id"]), "matter_id": matter_id, "name": client_obj.get("name"),
            "role": "Client", "type": client_obj.get("type"), "is_client": 1,
        }, ("id", "matter_id"))
        counts["contact"] += 1
    for rel in fetch_with_fallback(client, "relationships.json", {"matter_id": matter_id},
                                   RELATIONSHIP_FIELDS, "relationships"):
        db.save_raw(conn, "relationship", rel, matter_id)
        contact = rel.get("contact") or {}
        if not contact.get("id"):
            continue
        db.upsert(conn, "contacts", {
            "id": str(contact["id"]), "matter_id": matter_id, "name": contact.get("name"),
            "role": rel.get("description"), "type": contact.get("type"),
            "email": normalize.name_of(contact.get("primary_email_address")) if isinstance(
                contact.get("primary_email_address"), dict) else contact.get("primary_email_address"),
            "phone": normalize.name_of(contact.get("primary_phone_number")) if isinstance(
                contact.get("primary_phone_number"), dict) else contact.get("primary_phone_number"),
            "is_client": 0,
        }, ("id", "matter_id"))
        counts["contact"] += 1
    conn.commit()

    # 3. Notes, communications, tasks, calendar, activities -> events
    for source_type, path, extra_params, field_sets in RESOURCES:
        records = fetch_with_fallback(client, path, {**base_params, **extra_params}, field_sets, source_type)
        for rec in records:
            db.save_raw(conn, source_type, rec, matter_id)
            db.upsert(conn, "events", normalize.NORMALIZERS[source_type](matter_id, rec), ("id",))
        counts[source_type] += len(records)
        conn.commit()

    # 4. Documents: metadata, download, text extraction
    docs = fetch_with_fallback(client, "documents.json", base_params, DOCUMENT_FIELDS, "documents")
    config.DOCS_DIR.mkdir(parents=True, exist_ok=True)
    for rec in docs:
        db.save_raw(conn, "document", rec, matter_id)
        doc_id = str(rec["id"])
        info = {"text": "", "page_count": None, "text_chars": 0, "needs_ocr": False, "error": None}
        local_path = None
        existing = conn.execute("SELECT * FROM documents WHERE id=? AND matter_id=?",
                                (doc_id, matter_id)).fetchone()
        unchanged = existing and existing["updated_at"] == rec.get("updated_at") and existing["local_path"]
        if (skip_docs or unchanged) and existing:
            # Keep what we already extracted instead of wiping it
            info = {"text": existing["text"] or "", "page_count": existing["page_count"],
                    "text_chars": existing["text_chars"] or 0, "needs_ocr": bool(existing["needs_ocr"]),
                    "error": existing["error"]}
            local_path = existing["local_path"]
        elif not skip_docs:
            local_path = config.DOCS_DIR / f"{doc_id}_{safe_filename(rec.get('name'))}"
            try:
                client.download(f"documents/{doc_id}/download", local_path)
                info = extract_text(local_path, rec.get("content_type"))
            except ClioHTTPError as exc:
                info["error"] = f"download failed: {exc.status}"
                local_path = None
        db.upsert(conn, "documents", {
            "id": doc_id, "matter_id": matter_id, "name": rec.get("name"),
            "content_type": rec.get("content_type"),
            "category": normalize.name_of(rec.get("document_category")),
            "folder": normalize.name_of(rec.get("parent")),
            "local_path": str(local_path) if local_path else None,
            "page_count": info["page_count"], "text_chars": info["text_chars"],
            "needs_ocr": int(bool(info["needs_ocr"])), "text": info["text"], "error": info["error"],
            "created_at": rec.get("created_at"), "updated_at": rec.get("updated_at"),
        }, ("id", "matter_id"))
        db.upsert(conn, "events", normalize.document(matter_id, rec, info["text"], info["needs_ocr"],
                                                     info["page_count"]), ("id",))
        counts["document"] += 1
        if info["needs_ocr"]:
            counts["document_needs_ocr"] += 1
        if info["error"]:
            counts["document_error"] += 1
        conn.commit()

    conn.execute("UPDATE sync_runs SET finished_at=?, counts=? WHERE id=?",
                 (db.now_iso(), json.dumps(counts), run_id))
    conn.commit()
    return counts


def main(argv=None):
    parser = argparse.ArgumentParser(description="Ingest a Clio matter (read-only).")
    parser.add_argument("--matter-id")
    parser.add_argument("--query", help="search text to find the matter")
    parser.add_argument("--list", action="store_true", help="list matters and exit")
    parser.add_argument("--incremental", action="store_true")
    parser.add_argument("--skip-docs", action="store_true")
    args = parser.parse_args(argv)

    client = ClioReadOnlyClient()
    if args.list:
        print_matters(list_matters(client, args.query))
        return

    conn = db.connect()
    db.init_db(conn)
    matter_id = resolve_matter_id(client, args)
    counts = ingest(client, conn, matter_id, args.incremental, args.skip_docs)

    print("\nSynced:")
    for key, value in sorted(counts.items()):
        print(f"  {key:<20} {value}")
    total = conn.execute("SELECT COUNT(*) FROM events WHERE matter_id=?", (matter_id,)).fetchone()[0]
    print(f"  {'events (total)':<20} {total}")
    print(f"  {'API requests':<20} {client.request_count}")
    print(f"\nDatabase: {config.DB_PATH}")


if __name__ == "__main__":
    sys.exit(main())
