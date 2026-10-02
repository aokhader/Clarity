# Progress

This file holds shared state. Each track's checklist lives in `docs/tracks/` and is edited only by its owner. Update this file at sync points.

## Status

- **Phase:** M0, not started
- **Fixed times (PT):** integration 2:45 PM, feature freeze 3:15 PM, submit before 4:00 PM

## Plan

```
M0 Foundation (one person)
        |
   +----+----+----------------+
   |         |                |
Track A   Track B          Track C
Pipeline  Firm view        Provider side
   |         |                |
   +--- S1 --+------ S2 ------+--- S3
        |
Integration 2:45 PM -> M6 Polish -> freeze 3:15 PM -> M7 Submission
```

How the split works is in `docs/parallel.md`.

## M0 Foundation (30 min)

One person builds the skeleton and the contracts. Nothing in the tracks starts until every box here is checked, because the tracks depend on these files not moving.

- [ ] Repository, `.gitignore`, `.env` from `.env.example`
- [ ] Backend skeleton: FastAPI app, config, database session, CLI entry point
- [ ] `models.py`: every table in `docs/architecture.md`
- [ ] `schemas.py`: response models for every route, fact kinds, and the fact payload models
- [ ] One empty router file per track, all registered in `main.py`
- [ ] Frontend skeleton: Vite, Tailwind theme tokens, shadcn/ui, routes for `/matters/:id` and `/p/:token`, `/api` proxy, `src/api/types.ts` mirroring `schemas.py`
- [ ] `backend/tests/fixtures/synthetic_matter.py` and `cli seed-dev` (requirements in `docs/parallel.md`)
- [ ] Pushed to `main`; teammates clone and run `seed-dev`

Meanwhile, the other two people:

- [ ] Clio trial account, Sapini loaded through the Swans setup app, developer application with read permissions, credentials to Track A's owner
- [ ] OpenAPI spec saved to `docs/reference/clio-openapi.json`; field names in `docs/clio-api.md` confirmed or corrected
- [ ] Look through Sapini in Clio: how many documents and pages, which tabs hold data, which custom fields exist. Add what matters to Known issues.
- [ ] Ask the attorneys in the room where they draw the sharing line; adjust the visibility defaults in `docs/architecture.md` before C1 starts

## Tracks

| Track | Owner | Checklist | State |
|---|---|---|---|
| A: Pipeline | [name] | `docs/tracks/a-pipeline.md` | not started |
| B: Firm view | [name] | `docs/tracks/b-firm.md` | not started |
| C: Provider side | [name] | `docs/tracks/c-provider.md` | not started |

## Sync points

- [ ] S1: real sources and structured facts in a snapshot
- [ ] S2: document facts, page images, quotes
- [ ] S3: field mapping, KPIs, significance, brief
- [ ] Integration at 2:45 PM: clean run from `cli reset` on Track A's machine

## If behind at a sync point, cut in this order

1. The share composer becomes a one-click share with default settings. Keep the server-side filter and the provider page.
2. Drop the since-you-last-opened block.
3. Drop the second-read verification. Keep the quote check and confidence flags.
4. Drop timeline filters and search.

## M6 Polish (2:45 to 3:15 PM, everyone)

- [ ] Walk the clip script in `docs/submission.md` on the integrated build
- [ ] Loading, empty, and error states on the screens the clip shows
- [ ] Fix only what blocks the clip

## M7 Submission (3:15 PM to before 4:00 PM)

- [ ] README final (Track C)
- [ ] 90-second clip recorded on Sapini and uploaded with public access
- [ ] Form answers final, cost figure from `/api/ops/cost`, stubs collected from all three track files
- [ ] Final commit pushed; form submitted

## Decisions

One line each: what and why.

- FastAPI, SQLite, and a Vite React frontend on localhost: fastest path, and the brief says localhost can win.
- Visibility is decided by code from fact kind, default-deny: a model must not be the security boundary.
- Custom fields are mapped to KPI slots by a cached model call: field names differ per firm and must not appear in code.
- Three tracks split on the fact store, with a synthetic seed and snapshots: B and C never wait on the pipeline.

## Stubs and shortcuts (shared)

Track-specific ones live in the track files. Everything is disclosed on the submission form.

- No real authentication for firm users: seeded stub accounts with a header-based switcher.
- `cli seed-dev` loads an invented matter for development and tests. The demo runs on a live Clio sync.

## Known issues

- None yet.

## Cost log

Track A fills this from `/api/ops/cost` after each full digest.

| Run | Pages | Model calls | Tokens in | Tokens out | Cost |
|---|---|---|---|---|---|
