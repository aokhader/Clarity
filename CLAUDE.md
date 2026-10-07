# Clarity

Clarity turns one personal-injury case file in Clio Manage into two views: a 90-second brief for the law firm's team, and a scoped status page for the medical providers treating the client on lien. It is our entry in the Swans Applied AI Hackathon (Law-Di-Gras, San Diego, October 2, 2026).

Swans screens every repository before judging: does it run, does it work on the Sapini matter, is the output generated or hardcoded, and how is it engineered. Only the top 7 teams present. The finalists are judged by trial attorneys and AI engineers. Write code that survives that reading.

## Constraints that never bend

1. **Clio is read-only.** The rules disqualify builds that write or update case data through the API. The Clio client exposes GET only and raises on any other method. All of our own state lives in our own database.
2. **No case data in the codebase.** No names, dates, amounts, custom-field labels, or document titles from the Sapini matter in code, prompts, seeds, or the frontend. The pipeline must give a sensible result for any matter ID. Reviewers look for this specifically.
3. **Every displayed fact has a source.** A fact with no `source_id` (plus `page_no` and `quote` for documents) is not rendered. Attorneys told the organizers: "If a date is on screen, I need to see where it came from."
4. **The provider boundary is enforced in the API.** Provider endpoints return only allowlisted, shared facts. Never send internal facts to the browser and hide them in the UI.
5. **No model calls when a page loads.** Digest once, store the result, serve from the database. Re-digest only what changed.
6. **Time.** The hackathon closed on October 2. The trial's feature freeze is the time in `PLAN.md`; after it, only fixes, checks and the README.

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

# checks a screener would run (from the repository root)
bash scripts/check.sh
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

## Team (kit trial)

The hackathon's three tracks are closed; their history is in `docs/parallel.md`, `docs/progress.md` and `docs/tracks/`. Work now runs as a team of agent roles from the hackathon kit.

The human is the **Manager** and makes product calls. The **lead** session (no role) keeps PLAN.md and DECISIONS.md, integrates, and decides what to bring to the Manager. Every other session has one role, defined in `.claude/agents/<role>.md`, and edits only the paths `.claude/ownership.json` gives it. A PreToolUse hook enforces this when the session was started with `KIT_ROLE` set. Start a worker with `/kickoff <role>`, and update with `/status`.

| File | Written by | Holds |
|---|---|---|
| `PLAN.md` | lead | goal, demo moments, backlog with owners, milestones, cut order |
| `STATUS.md` | every role, its own row only | now, next, blocked on, needs decision, updated at; the stubs list |
| `DECISIONS.md` | lead only | numbered decisions (D1, D2, ...) with time and reason |
| `HANDOFF.md` | a session about to clear its context (gitignored) | done, in progress, next, gotchas |
| `docs/briefs/`, `docs/reviews/` | researcher; critic and reviewer | sourced briefs; ranked findings |

A role that needs a change in a path it does not own writes it under "Blocked on" in its STATUS row and tells the user. Commit only your own paths: `git commit -m "..." -- <paths>`. The contract (`schemas.py` and `types.ts`) belongs to backend and changes in one commit.

## Context files

Always loaded:

@PLAN.md
@docs/workflow.md
@docs/code-standards.md

Read the matching file before starting work in that area:

| Working on | Read first |
|---|---|
| Any work in the kit trial | `STATUS.md`, `DECISIONS.md`, and your role file in `.claude/agents/` |
| Known issues, past decisions, the Track A review | `docs/progress.md` and `docs/tracks/` |
| Scope, users, flows, what to cut | `docs/project.md` |
| Data model, API routes, visibility rules | `docs/architecture.md` |
| Anything that calls Clio | `docs/clio-api.md` |
| PDF parsing, extraction, the brief, cost | `docs/digest-pipeline.md` |
| Any screen or component | `docs/ui.md` |
| README, clip, submission form | `docs/submission.md` |
