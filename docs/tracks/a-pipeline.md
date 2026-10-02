# Track A: Pipeline

**Owner:** [name]
**Read first:** `docs/clio-api.md`, `docs/digest-pipeline.md`
**Needs:** Clio credentials and model keys in `.env`

## Status

- **Now:** A1
- **Blocked:** nothing

## Checklist

### A1 Sync (35 min)
- [ ] OAuth through `cli auth`, tokens stored and refreshed
- [ ] GET-only client: fields, paging, rate limiting, write guard, test for the guard
- [ ] `cli sync` pulls matter, relationships, contacts, notes, communications, tasks, calendar, activities
- [ ] Document list and downloads to `data/files/`
- [ ] Re-sync skips unchanged records; `sync_runs` row written

### A2 Structured facts (15 min)
- [ ] Stage 1 facts from tasks, calendar, activities, matter, communications
- [ ] **S1: publish snapshot**

### A3 Pages and model wrapper (25 min)
- [ ] Text layer detection, PNG rendering, content hashes
- [ ] `llm.py` with cache, cost logging, and one retry on schema failure

### A4 Extraction and verification (40 min)
- [ ] Per-page and per-record extraction with the schema in `docs/digest-pipeline.md`
- [ ] Quote check, second read, date sanity, provider resolution
- [ ] Second `cli digest` run makes zero model calls
- [ ] **S2: publish snapshot**

### A5 Merge (40 min)
- [ ] Role and field mapping; KPI facts from custom fields
- [ ] Deduplication, significance scoring, cross-checks
- [ ] Brief with cited sentences
- [ ] **S3: publish snapshot**

### A6 Ops endpoints (10 min)
- [ ] Sync and digest triggers and status, cost endpoint, in `api/ops.py`
- [ ] Fill the cost log in `docs/progress.md`

## If behind

This track is the critical path: its items add up to about 2 hours 45 minutes, and tracks B and C need its snapshots. Cut in this order, and tell the team at the next sync point:

1. Incremental re-sync. A full sync each time is acceptable for one matter.
2. The second read for money and dates. Keep the quote check and mark scan-derived values as medium confidence.
3. Deduplication and cross-checks in the merge step.
4. Non-PDF document types.

Never cut page-level citations, the model-call cache, or cost logging.

## Contract obligations

Tracks B and C read what this track writes. Every fact must match the payload model for its kind in `schemas.py` and carry `source_id`, plus `page_no` and `quote` for documents. If the real data forces a new kind or a payload change, follow the contract-change steps in `docs/parallel.md` before writing the code.

## Stubs and shortcuts

- None yet.

## Known issues

- None yet.
