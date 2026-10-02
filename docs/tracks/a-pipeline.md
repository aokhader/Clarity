# Track A: Pipeline

**Owner:** Charles
**Read first:** `docs/clio-api.md`, `docs/digest-pipeline.md`
**Needs:** Clio credentials and model keys in `.env`

## Status

- **Now:** first live run on Sapini (`cli auth`, `cli sync`, `cli digest`), then S1 snapshot
- **Blocked:** Clio developer app credentials and the model key in `.env`

## Checklist

### A1 Sync (35 min)
- [x] OAuth through `cli auth`, tokens stored and refreshed
- [x] GET-only client: fields, paging, rate limiting, write guard, test for the guard
- [x] `cli sync` pulls matter, relationships, contacts, notes, communications, tasks, calendar, activities
- [x] Document list and downloads to `data/files/`
- [x] Re-sync skips unchanged records; `sync_runs` row written

### A2 Structured facts (15 min)
- [x] Stage 1 facts from tasks, calendar, activities, matter, communications
- [ ] **S1: publish snapshot**

### A3 Pages and model wrapper (25 min)
- [x] Text layer detection, PNG rendering, content hashes
- [x] `llm.py` with cache, cost logging, and one retry on schema failure

### A4 Extraction and verification (40 min)
- [x] Per-page and per-record extraction with the schema in `docs/digest-pipeline.md`
- [x] Quote check, second read, date sanity, provider resolution
- [x] Second `cli digest` run makes zero model calls
- [ ] **S2: publish snapshot**

### A5 Merge (40 min)
- [x] Role and field mapping; KPI facts from custom fields
- [x] Deduplication, significance scoring, cross-checks
- [x] Brief with cited sentences
- [ ] **S3: publish snapshot**

### A6 Ops endpoints (10 min)
- [x] Sync and digest triggers and status, cost endpoint, in `api/ops.py`
- [ ] Fill the cost log in `docs/progress.md`

Verified so far against an invented matter (fake Clio transport, fake model): sync and
re-sync, two digests (second one 0 model calls, fact ids unchanged), a fabricated quote
dropped, a scanned page's money read twice, a brief sentence with an unknown fact id
dropped, medical charges split from firm spend. Not yet run against live Clio or a real model.

## Decisions

- Mapping (roles, fields, activities) runs before extraction, not inside merge: the extractor needs the provider list to attribute facts.
- Non-time ledger entries are classified by a cached model call into firm costs (`expense`) and the client's medical charges (`medical_bill`). Some firms log provider charges in the expense ledger, which would otherwise inflate firm spend.
- Custom fields mapped to `case_value`, `medical_specials`, `date_of_incident`, `statute_of_limitations` become facts in code (`origin = code`). Coverage, policy limits, and unmapped fields go through record extraction, since they are multi-part free text.
- Code-readable slots become `case_value`, `medical_specials`, `incident`, and `deadline` (statute of limitations) facts on the matter source. The firm's stage is mapped to a canonical `CaseStage` in the same cached call as the fields.
- Custom fields code cannot read (coverage, policy limits, unmapped) go to record extraction as one input sourced to the matter.
- The specials cross-check stores the sum of medical bills as an `alt_values` entry on the `medical_specials` fact when they disagree.
- Every payload goes through `schemas.validate_payload`; keys a kind does not allow are dropped from model output before validation.
- Text-layer PDF pages are sent as text only; images are sent for scans. Cuts cost and keeps the quote check exact.
- A fact set identical to the stored one is not rewritten, so fact ids stay stable across runs (shares refer to them).
- `significance = 0` means not scored yet; scored facts are stored with at least 1.
- Model wire format is set by `LLM_PROVIDER` (anthropic or openai) over httpx, so no SDK dependency was added.
- `cli auth` runs its own short-lived listener on the redirect URI, so the API server must not hold port 8000 during auth.

## Contract obligations

Tracks B and C read what this track writes. Every fact must match the payload model for its kind in `schemas.py` and carry `source_id`, plus `page_no` and `quote` for documents. If the real data forces a new kind or a payload change, follow the contract-change steps in `docs/parallel.md` before writing the code.

## Stubs and shortcuts

- Clio's personal-injury endpoints (`/medical_records_details.json`, `/damages.json`) are not synced yet; bills come from documents, notes, and the expense ledger.
- Each Clio request falls back to a smaller field list if Clio rejects a name; the first list is the spec-verified one from `docs/clio-api.md`.
- Calendar entries all become `deadline` facts, including treatment appointments.
- Time entries produce no facts; firm spend counts non-time entries only, as `docs/clio-api.md` specifies.

## Known issues

- Deduplication deletes duplicate facts, so a source that had a duplicate gets new fact ids on the next run.
