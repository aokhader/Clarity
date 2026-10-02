# Progress

Update this file in the same commit as the work it describes.

## Status

- **Now:** M0 done except the Clio developer application, which needs a person with the Clio account
- **Next:** M1
- **Blocked:** M1 needs `CLIO_CLIENT_ID` and `CLIO_CLIENT_SECRET` in `.env`
- **Fixed times (PT):** feature freeze 3:15 PM, submit before 4:00 PM

## Milestones

Budgets are targets and total about 4 hours of building before the freeze. At twice the budget, stop and report options.

If behind schedule, cut in this order:

1. The share composer becomes a one-click share with default settings. Keep the server-side filter and the provider page.
2. Drop the since-you-last-opened block.
3. Drop the second-read verification. Keep the quote check and confidence flags.
4. Drop timeline filters and search.

### M0 Setup (15 min)
- [x] Repository, `.gitignore`, `.env` from `.env.example`
- [x] Backend skeleton: FastAPI app, config, database, models, CLI entry point
- [x] Frontend skeleton: Vite, Tailwind, shadcn/ui, router, `/api` proxy
- [ ] Clio developer application created with read permissions; credentials in `.env`
- [x] OpenAPI spec saved to `docs/reference/clio-openapi.json`; field names in `docs/clio-api.md` confirmed or corrected

### M1 Sync (35 min)
- [ ] OAuth flow through `cli auth`, tokens stored and refreshed
- [ ] GET-only client with fields, paging, rate limiting, and the write guard
- [ ] `cli sync` pulls matter, relationships, contacts, notes, communications, tasks, calendar, activities
- [ ] Document list and downloads to `data/files/`
- [ ] Re-sync skips unchanged records; `sync_runs` row written
- [ ] Test: non-GET raises

### M2 Structured facts and firm skeleton (40 min)
- [ ] Stage 1 facts from tasks, calendar, activities, matter, communications
- [ ] Endpoints: matter header, actions, feed, fact source
- [ ] Firm page with header, action board, feed, and source drawer on real data
- [ ] Database schema frozen at the end of this milestone

### M3 Documents (50 min)
- [ ] Pages: text layer detection, PNG rendering, hashes
- [ ] `llm.py` wrapper with cache and cost logging
- [ ] Per-page and per-record extraction with the schema in `docs/digest-pipeline.md`
- [ ] Verification: quote check, second read, provider resolution
- [ ] Source drawer shows the page image and quote
- [ ] Second `cli digest` run makes zero model calls

### M4 Brief and ranking (40 min)
- [ ] Role and field mapping; KPI facts from custom fields
- [ ] Deduplication, significance scoring, cross-checks
- [ ] Brief generation with cited sentences
- [ ] KPI strip, brief, injuries list, ranked feed with timeline toggle
- [ ] Since-you-last-opened block with seeded users

### M5 Provider side (40 min)
- [ ] `visible_facts_for_share` with tests
- [ ] Share create, preview, patch; token route with opened event
- [ ] Provider page at `/p/:token`
- [ ] Share composer with toggles, hide, and live preview
- [ ] Providers panel shows share and opened status

### M6 Polish (15 min, ends at 3:15 PM)
- [ ] Loading, empty, and error states
- [ ] Footer: sync time, digest cost, re-sync
- [ ] Full run from `cli reset` on a clean checkout

### M7 Submission (45 min, ends before 4:00 PM)
- [ ] README: what it is, how to run, architecture, what is stubbed
- [ ] 90-second clip recorded on Sapini and uploaded with public access
- [ ] Form answers drafted from `docs/submission.md`, cost figure taken from `/api/ops/cost`
- [ ] Final commit pushed; form submitted

## Decisions

Record the date-free what and why, one line each.

- FastAPI, SQLite, and a Vite React frontend on localhost: fastest path, and the brief says localhost can win.
- Visibility is decided by code from fact kind, default-deny: a model must not be the security boundary.
- Custom fields are mapped to KPI slots by a cached model call: field names differ per firm and must not appear in code.
- `pydantic-settings` loads `.env` into typed settings: the one dependency added beyond the stack list, approved.
- `DATA_DIR` resolves against the repository root and the database path derives from it: the CLI and the server always agree on one location. `DATABASE_URL` is gone.
- `sources` is unique on `(matter_id, clio_type, clio_id)` with a string `clio_id`: contacts and custom fields are account-level in Clio, and calendar entry ids are strings.
- `llm_calls` doubles as the response cache (`cache_key`, `response_json`) and stores cost as integer micro-dollars: one table for cache and cost, with exact sums.
- Every Clio request pins `X-API-VERSION` from config: a change of Clio's default minor version cannot shift field meanings.
- Dark mode is out of scope, so shadcn's `dark:` classes are bound to a `.dark` class we never set, not to the OS colour scheme.

## Stubs and shortcuts

Everything here is disclosed on the submission form.

- Firm users are seeded stub accounts with a header-based switcher; no real authentication. (`backend/app/db.py`)
- Seeded `last_opened_at` values so the changes block has content on first run. (`backend/app/db.py`)
- Until M1 and M2, `cli auth`, `cli sync`, and `cli digest` print "not built yet" and exit with code 2. (`backend/app/cli.py`)

## Known issues

- The paging envelope (`meta.paging.next`) and the rate-limit headers come from Clio's docs, not the spec. Confirm both on the first real response in M1. (`docs/clio-api.md`)
- Open decision: Clio's personal-injury endpoints (`/medical_records_details.json`, `/damages.json`) hold structured bills and record-request status per provider, but are not in the sync order. Neither accepts `matter_id`, so the sync would page the whole account and filter. (`docs/clio-api.md`)

## Cost log

Fill from `/api/ops/cost` after each full digest.

| Run | Pages | Model calls | Tokens in | Tokens out | Cost |
|---|---|---|---|---|---|
