"""SQLite storage. This file is the data contract shared by ingest, the AI digest, and the API.

Clio is read-only for us, so everything we derive (digests, facts, views, shares) lives here.
"""
import json
import sqlite3
from datetime import datetime, timezone

from .config import DB_PATH

SCHEMA = """
-- Every record exactly as Clio returned it (for debugging and re-normalizing without re-fetching)
CREATE TABLE IF NOT EXISTS raw_records (
    resource    TEXT NOT NULL,
    clio_id     TEXT NOT NULL,
    matter_id   TEXT,
    json        TEXT NOT NULL,
    fetched_at  TEXT NOT NULL,
    PRIMARY KEY (resource, clio_id)
);

CREATE TABLE IF NOT EXISTS matters (
    id                  TEXT PRIMARY KEY,
    display_number      TEXT,
    description         TEXT,
    status              TEXT,
    practice_area       TEXT,
    open_date           TEXT,
    close_date          TEXT,
    client_id           TEXT,
    client_name         TEXT,
    responsible_attorney TEXT,
    created_at          TEXT,
    updated_at          TEXT,
    synced_at           TEXT
);

-- People and organizations attached to the matter, with their role on the case
CREATE TABLE IF NOT EXISTS contacts (
    id          TEXT NOT NULL,
    matter_id   TEXT NOT NULL,
    name        TEXT,
    role        TEXT,      -- e.g. "Client", "Treating provider, orthopedics"
    type        TEXT,      -- Person / Company
    email       TEXT,
    phone       TEXT,
    is_client   INTEGER DEFAULT 0,
    PRIMARY KEY (id, matter_id)
);

-- Matter custom fields, joined to their names (case value, policy limits, specials...)
CREATE TABLE IF NOT EXISTS custom_fields (
    id          TEXT NOT NULL,   -- custom_field_value id (source_id for provenance)
    matter_id   TEXT NOT NULL,
    name        TEXT,
    field_type  TEXT,
    value       TEXT,
    PRIMARY KEY (id, matter_id)
);

CREATE TABLE IF NOT EXISTS documents (
    id            TEXT NOT NULL,
    matter_id     TEXT NOT NULL,
    name          TEXT,
    content_type  TEXT,
    category      TEXT,
    folder        TEXT,
    local_path    TEXT,
    page_count    INTEGER,
    text_chars    INTEGER,
    needs_ocr     INTEGER DEFAULT 0,   -- 1 = scanned, text layer empty
    text          TEXT,                -- extracted text with [page N] markers
    error         TEXT,
    created_at    TEXT,
    updated_at    TEXT,
    PRIMARY KEY (id, matter_id)
);

-- One unified stream: every note, email, task, calendar entry, expense and document.
-- id = "<source_type>:<clio_id>"  -> this is the source_id every derived fact points back to.
CREATE TABLE IF NOT EXISTS events (
    id           TEXT PRIMARY KEY,
    matter_id    TEXT NOT NULL,
    source_type  TEXT NOT NULL,   -- note | communication | task | calendar_entry | activity | document | custom_field
    source_id    TEXT NOT NULL,   -- Clio id of the record
    kind         TEXT,            -- finer type: email, phone_call, expense, time_entry, ...
    date         TEXT,            -- ISO date/datetime used for the timeline
    author       TEXT,
    title        TEXT,
    text         TEXT,
    extra        TEXT,            -- JSON: status, due_at, amount, participants...
    updated_at   TEXT,
    synced_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_matter_date ON events (matter_id, date);

-- AI output per event (written by the digest step). input_hash lets us skip unchanged events.
CREATE TABLE IF NOT EXISTS event_digest (
    event_id    TEXT PRIMARY KEY,
    importance  INTEGER,          -- 1..5
    category    TEXT,
    shareable   INTEGER,          -- 1 = safe to show a medical provider
    waiting_on  TEXT,             -- provider | insurer | client | court | firm | NULL
    summary     TEXT,
    reason      TEXT,
    model       TEXT,
    input_hash  TEXT,
    created_at  TEXT
);

-- Extracted facts. Every fact must carry the quote and the event id it came from.
CREATE TABLE IF NOT EXISTS facts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    matter_id      TEXT NOT NULL,
    kind           TEXT NOT NULL,  -- case_value | coverage | medical_specials | firm_spend | injury | ...
    label          TEXT,
    value          TEXT,
    value_numeric  REAL,
    quote          TEXT,
    source_event_id TEXT,          -- events.id
    page           INTEGER,        -- for documents
    confidence     REAL,
    model          TEXT,
    created_at     TEXT
);

-- Token and cost log for every model call (feeds the cost-per-case answer)
CREATE TABLE IF NOT EXISTS llm_calls (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    matter_id      TEXT,
    purpose        TEXT,
    model          TEXT,
    input_tokens   INTEGER,
    output_tokens  INTEGER,
    cost_usd       REAL,
    created_at     TEXT
);

CREATE TABLE IF NOT EXISTS sync_runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    matter_id    TEXT,
    mode         TEXT,
    started_at   TEXT,
    finished_at  TEXT,
    counts       TEXT
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect(path=DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def upsert(conn: sqlite3.Connection, table: str, row: dict, keys: tuple) -> None:
    """Insert or update one row; `keys` are the primary key columns."""
    cols = list(row.keys())
    placeholders = ", ".join("?" for _ in cols)
    updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c not in keys)
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) ON CONFLICT ({', '.join(keys)}) DO "
    sql += f"UPDATE SET {updates}" if updates else "NOTHING"
    values = [json.dumps(v) if isinstance(v, (dict, list)) else v for v in row.values()]
    conn.execute(sql, values)


def save_raw(conn, resource: str, record: dict, matter_id) -> None:
    upsert(conn, "raw_records", {
        "resource": resource,
        "clio_id": str(record.get("id")),
        "matter_id": str(matter_id) if matter_id is not None else None,
        "json": json.dumps(record),
        "fetched_at": now_iso(),
    }, ("resource", "clio_id"))


def last_sync_time(conn, matter_id: str):
    row = conn.execute(
        "SELECT started_at FROM sync_runs WHERE matter_id=? AND finished_at IS NOT NULL "
        "ORDER BY id DESC LIMIT 1", (matter_id,)).fetchone()
    return row["started_at"] if row else None
