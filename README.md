# Clarity

Clarity turns one personal-injury matter in Clio Manage into two views: a 90-second brief for the law firm, and a scoped status page for the medical providers treating the client on lien. Every fact on screen links to the record or PDF page it came from. Clio is read-only: the app never writes to it.

Built for the Swans Applied AI Hackathon (Law-Di-Gras, San Diego, 2026).

## Status

Foundation is done (M0): the schema, the API contracts, and an invented development matter are in place. Clio sync, the digest pipeline, and both views are being built in three parallel tracks; `docs/progress.md` tracks them.

## Run it

Requires Python 3.11+ and Node 20+. Copy `.env.example` to `.env` at the repository root and fill in the Clio and model settings.

```bash
# backend (from backend/)
conda activate LawDiGras             # or any Python 3.11+ virtual environment
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
pytest -q
```

```bash
# frontend (from frontend/)
npm install
npm run dev                          # http://localhost:5173, proxies /api to port 8000
npm run typecheck
```

`python -m app.cli seed-dev` loads an invented matter for development (the demo runs on a live Clio sync), and `python -m app.cli reset` deletes the database and downloaded files. The `auth`, `sync`, and `digest` commands are being built.

## Architecture

```
Clio Manage (read-only) -> sync -> digest pipeline -> fact store (SQLite) -> API -> firm view
                                                                                 -> provider view
```

One store of sourced facts feeds both views. The provider view is the same data behind a stricter, default-deny filter applied in the API. Details are in `docs/architecture.md`.

- `backend/`: FastAPI, SQLAlchemy 2, SQLite, Pydantic 2
- `frontend/`: Vite, React, TypeScript (strict), Tailwind, shadcn/ui, TanStack Query, React Router
- `data/`: the database, downloaded files, and rendered pages (gitignored)

## Stubs and shortcuts

These are tracked in `docs/progress.md` and disclosed on the submission form.

- There is no real authentication. Firm users will be seeded stub accounts.
- Until their milestones land, `cli auth`, `cli sync`, and `cli digest` print "not built yet".
