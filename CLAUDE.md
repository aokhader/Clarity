# Case Digest (working title)

Case Digest turns one personal-injury case file in Clio Manage into two views: a 90-second brief for the law firm's team, and a scoped status page for the medical providers treating the client on lien. It is our entry in the Swans Applied AI Hackathon (Law-Di-Gras, San Diego, October 2, 2026).

Swans screens every repository before judging: does it run, does it work on the Sapini matter, is the output generated or hardcoded, and how is it engineered. Only the top 7 teams present. The finalists are judged by trial attorneys and AI engineers. Write code that survives that reading.

## Constraints that never bend

1. **Clio is read-only.** The rules disqualify builds that write or update case data through the API. The Clio client exposes GET only and raises on any other method. All of our own state lives in our own database.
2. **No case data in the codebase.** No names, dates, amounts, custom-field labels, or document titles from the Sapini matter in code, prompts, seeds, or the frontend. The pipeline must give a sensible result for any matter ID. Reviewers look for this specifically.
3. **Every displayed fact has a source.** A fact with no `source_id` (plus `page_no` and `quote` for documents) is not rendered. Attorneys told the organizers: "If a date is on screen, I need to see where it came from."
4. **The provider boundary is enforced in the API.** Provider endpoints return only allowlisted, shared facts. Never send internal facts to the browser and hide them in the UI.
5. **No model calls when a page loads.** Digest once, store the result, serve from the database. Re-digest only what changed.
6. **Time.** Feature freeze at 3:15 PM PT. Repository, clip, and form are submitted before 4:00 PM PT. The close is hard, with no grace window.

## Stack

- Backend: Python 3.11+, FastAPI, SQLAlchemy 2, SQLite, httpx, PyMuPDF, Pydantic 2
- Frontend: Vite, React, TypeScript (strict), Tailwind, shadcn/ui, TanStack Query, React Router
- Models: one vision-capable model for per-page extraction and one stronger model for the merge step, both set in `.env`
- Runs on localhost. Deployment is out of scope unless every milestone is done.

## Commands

Create these in milestone M0 and keep them working.

```bash
# backend (from backend/)
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
python -m app.cli auth      # one-time Clio OAuth, stores tokens in the database
python -m app.cli sync      # pull the matter from Clio into sources
python -m app.cli digest    # pages -> facts -> brief (cached, incremental)
python -m app.cli seed-dev  # load the synthetic matter for development without Clio
python -m app.cli reset     # drop the database and the data/ directory
pytest -q

# frontend (from frontend/)
npm install
npm run dev                 # Vite on 5173, proxies /api to 8000
npm run typecheck
```

## Layout

```
backend/app/
  main.py  config.py  db.py  models.py  schemas.py  cli.py
  clio/      client.py  oauth.py  sync.py
  digest/    pages.py  structured.py  extract.py  merge.py  verify.py  llm.py  prompts/
  services/  matter_queries.py  visibility.py  shares.py
  api/       matters.py  facts.py  shares.py  provider.py  ops.py
backend/tests/
  fixtures/synthetic_matter.py
frontend/src/
  api/  lib/
  pages/       firm/  provider/
  components/  shared/  firm/  share/
data/        gitignored: app.db, files/, pages/
docs/
```

## Parallel tracks

After M0 the work runs as three tracks with separate owners: A (pipeline), B (firm view), C (provider side). A session works one track and edits only the paths that track owns. The track comes from `CLAUDE.local.md` or from the first message; if neither says, ask before editing anything. The split, the frozen contract files, and the sync points are in `docs/parallel.md`.

## Context files

Always loaded:

@docs/progress.md
@docs/workflow.md
@docs/code-standards.md

Read the matching file before starting work in that area:

| Working on | Read first |
|---|---|
| Any work after M0 | `docs/parallel.md` and your track file in `docs/tracks/` |
| Scope, users, flows, what to cut | `docs/project.md` |
| Data model, API routes, visibility rules | `docs/architecture.md` |
| Anything that calls Clio | `docs/clio-api.md` |
| PDF parsing, extraction, the brief, cost | `docs/digest-pipeline.md` |
| Any screen or component | `docs/ui.md` |
| README, clip, submission form | `docs/submission.md` |
