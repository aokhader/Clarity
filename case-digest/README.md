# Case Digest

Turns a live Clio Manage matter into a 90-second case digest for the firm, and a scoped, attorney-controlled view for treating medical providers.

**Clio is read-only input.** The Clio client can only send GET requests (`backend/clio_client.py` blocks every other HTTP method). Everything we derive lives in our own SQLite database.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Connect Clio (one command)

```bash
python -m backend.connect --ingest
```

It asks for credentials if none exist (an access token, or an OAuth app ID/secret), saves them to the git-ignored `.env`, verifies the connection, picks the matter, and pulls it.

Manual alternatives:

- **Access token:** paste it into `CLIO_ACCESS_TOKEN` in `.env`.
- **OAuth app:** create a developer application in Clio (redirect URI `http://127.0.0.1:8765/callback`), put its ID and secret in `.env`, then run:

  ```bash
  python -m backend.auth
  ```

Set `CLIO_BASE_URL` if the account is outside the US region.

## Ingest

```bash
python -m backend.ingest --list            # see matters in the account
python -m backend.ingest --query <name>    # pull one matter (all records + documents)
python -m backend.ingest --incremental     # only what changed since the last sync
```

This pulls the matter, its custom fields, contacts and roles, notes, communications, tasks, calendar entries, activities (time and expenses), and documents. Documents are downloaded and their text is extracted with `[page N]` markers. Scans with no text layer are flagged `needs_ocr`.

Explore any endpoint or field set:

```bash
python -m backend.probe notes.json --param matter_id=<id> --param type=Matter --fields "id,subject,detail"
```

## Data model (`backend/db.py`)

| Table | Purpose |
|---|---|
| `events` | One unified stream of every note, email, task, calendar entry, expense, document and custom field. `id = "<source_type>:<clio_id>"` is the provenance key. |
| `matters`, `contacts`, `custom_fields`, `documents` | Structured matter data |
| `event_digest` | AI importance, category, shareable flag, waiting-on, per event (`input_hash` skips unchanged events) |
| `facts` | Extracted facts (case value, coverage, injuries...), each with the quote and `source_event_id` |
| `llm_calls` | Token and cost log for every model call |
| `raw_records` | Clio responses as returned, for debugging |
| `sync_runs` | Ingest history, used for incremental sync |

## Architecture

```
Clio (GET only) -> ingest -> SQLite (events, docs, contacts) -> AI digest (cached) -> API -> Firm view / Provider portal
```
