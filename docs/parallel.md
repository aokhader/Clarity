# Parallel plan

After M0, the work splits into three tracks that run at the same time. This file defines who owns what, the contracts that make the split safe, and when the tracks meet.

## Why this split works

The fact store is the only thing the tracks share. Track A writes facts. Tracks B and C read them. Once the tables, the fact payloads, and the API response schemas are fixed in M0, nobody waits on anybody: B and C build against a synthetic seed until A's real data arrives.

## Tracks

| Track | Scope | Owns these paths | Checklist |
|---|---|---|---|
| A: Pipeline | Clio sync, PDF pages, extraction, verification, merge, brief, cost | `backend/app/clio/`, `backend/app/digest/`, `backend/app/api/ops.py`, sync and digest commands in `cli.py` | `docs/tracks/a-pipeline.md` |
| B: Firm view | Firm endpoints and every firm screen, the source drawer, shared UI pieces | `backend/app/api/matters.py`, `backend/app/api/facts.py`, `backend/app/services/matter_queries.py`, `frontend/src/pages/firm/`, `frontend/src/components/firm/`, `frontend/src/components/shared/` | `docs/tracks/b-firm.md` |
| C: Provider side | Visibility filter and tests, shares, provider page, share composer, providers panel, then submission material | `backend/app/services/visibility.py`, `backend/app/services/shares.py`, `backend/app/api/shares.py`, `backend/app/api/provider.py`, `frontend/src/pages/provider/`, `frontend/src/components/share/`, `README.md` | `docs/tracks/c-provider.md` |

Edit only the paths your track owns. If you need a change in someone else's path, ask the owner. If they are heads-down, make the smallest possible change and tell them right away.

## Contract files

These are written in M0 and frozen afterward, because every track depends on them:

- `backend/app/models.py`: tables
- `backend/app/schemas.py`: API response models and the fact payload models
- `frontend/src/api/types.ts`: the TypeScript mirror of `schemas.py`
- `backend/app/main.py`: registers all routers (each track's router file exists from M0, empty)
- `frontend/src/App.tsx` and the Tailwind theme: routes for both views and the design tokens
- `backend/tests/fixtures/synthetic_matter.py`: the seed

To change a contract file after M0:

1. Tell the team what and why before editing.
2. Make the change in one commit that updates every mirror (`schemas.py` and `types.ts` together).
3. Everyone pulls. If `models.py` changed, everyone runs `cli reset` and reloads data.

## Data during parallel work

**Synthetic seed.** `python -m app.cli seed-dev` loads a small invented matter from `backend/tests/fixtures/synthetic_matter.py` into the database through the same tables the pipeline writes. It must include every fact kind, two medical providers, internal and shareable facts, low-confidence and disagreeing facts, a note source, an email source, and a document source with at least two rendered pages. Names and details are invented and generic. The same fixture backs the test suite. It is development data only: the demo runs on a real sync, and the README says so.

**Snapshots.** Only Track A needs Clio and model credentials. At each sync point, A zips `data/` and passes it to B and C directly (AirDrop, USB, or a private share). B and C unzip it over their `data/` directory. This keeps everyone on identical facts and avoids paying for the digest three times.

```bash
# Track A
cd backend && zip -r ../data-snapshot.zip data
# Tracks B and C
cd backend && rm -rf data && unzip ../data-snapshot.zip
```

The snapshot contains a real person's medical and legal records. Never commit it, never put it behind a public link, and delete the copies after the event.

## Sync points

Each is a two-minute check-in: what landed, any contract change, anything being cut.

| Point | When | What A delivers | What B and C do |
|---|---|---|---|
| S1 | About 50 min after M0 | Snapshot with real sources and structured facts (tasks, deadlines, expenses, client contacts) | Switch from seed to snapshot. Fix whatever real data breaks. |
| S2 | About 115 min after M0 | Snapshot with document facts, page images, quotes | B checks the drawer on real scans. C checks bills and records per provider. |
| S3 | About 155 min after M0 | Snapshot with field mapping, KPIs, significance, brief | B checks brief, KPIs, feed. C checks stage and coverage on the provider page. |
| Integration | 2:45 PM PT, fixed | Clean run on A's machine: pull, `cli reset`, `auth`, `sync`, `digest`, both servers | Everyone walks the clip script together and fixes only what blocks it. |

Anything not working at 2:45 PM is cut using the order in `docs/progress.md`. The freeze stays at 3:15 PM.

## Git

- Everyone works on `main`. With disjoint paths, conflicts are rare, and there is no time for long-lived branches.
- Commit small. Run `git pull --rebase` before every push.
- Do not push a broken `main`: run `pytest -q` or `npm run typecheck` for the side you touched first.
- Never force-push.
- Each person updates only their own track file. `docs/progress.md` changes only at sync points.

## One Claude Code session per track

Each teammate creates a `CLAUDE.local.md` in the repository root (it is gitignored) so every session, including after a clear, knows its track:

```
This checkout works Track B. Edit only the paths Track B owns in docs/parallel.md.
@docs/tracks/b-firm.md
```

If that file is missing, say which track the session is on in the first message.

## Fewer than three people

- **Two people:** one takes Track A. The other takes Track B through B3, then C1 to C3, then returns to B4. Whoever finishes first takes C4 and C5.
- **Solo:** A1, A2, B1 to B3, A3, A4, A5, B4, C1 to C3, then the rest as time allows.
