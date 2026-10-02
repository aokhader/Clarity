# Progress

Update this file in the same commit as the work it describes.

## Status

- **Now:** M0, not started
- **Next:** M1
- **Blocked:** nothing
- **Fixed times (PT):** feature freeze 3:15 PM, submit before 4:00 PM

## Milestones

Budgets are targets and total about 4 hours of building before the freeze. At twice the budget, stop and report options.

If behind schedule, cut in this order:

1. The share composer becomes a one-click share with default settings. Keep the server-side filter and the provider page.
2. Drop the since-you-last-opened block.
3. Drop the second-read verification. Keep the quote check and confidence flags.
4. Drop timeline filters and search.

### M0 Setup (15 min)
- [ ] Repository, `.gitignore`, `.env` from `.env.example`
- [ ] Backend skeleton: FastAPI app, config, database, models, CLI entry point
- [ ] Frontend skeleton: Vite, Tailwind, shadcn/ui, router, `/api` proxy
- [ ] Clio developer application created with read permissions; credentials in `.env`
- [ ] OpenAPI spec saved to `docs/reference/clio-openapi.json`; field names in `docs/clio-api.md` confirmed or corrected

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

## Stubs and shortcuts

Everything here is disclosed on the submission form.

- Firm users are seeded stub accounts with a header-based switcher; no real authentication. (`backend/app/db.py`)
- Seeded `last_opened_at` values so the changes block has content on first run. (`backend/app/db.py`)

## Known issues

- None yet.

## Cost log

Fill from `/api/ops/cost` after each full digest.

| Run | Pages | Model calls | Tokens in | Tokens out | Cost |
|---|---|---|---|---|---|
