# Clarity

Clarity turns one personal-injury matter in Clio Manage into two views. The firm gets a brief it can read in 90 seconds: the story of the case in sentences, the numbers that matter, what is overdue, and what changed since the last visit. The medical providers treating the client on lien get a private status page that shows only what the attorney chooses to release: where the case stands, whether coverage is confirmed, what the firm needs from them, and their own bills and records. Every date, amount, and claim on either page links to the note, email, or PDF page it came from. Clio is read-only: the app never writes to it.

Built for the Swans Applied AI Hackathon (Law-Di-Gras, San Diego, October 2, 2026).

## Run it

Requires Python 3.11+ and Node 20+. Copy `.env.example` to `.env` at the repository root. It needs a Clio developer application with read permissions (`CLIO_CLIENT_ID`, `CLIO_CLIENT_SECRET`), the matter to find (`CLIO_MATTER_QUERY`), and a model key with the two model names and their prices per million tokens.

```bash
# backend (from backend/)
python -m venv .venv && source .venv/bin/activate   # or any Python 3.11+ environment
pip install -r requirements.txt
python -m app.cli auth        # one-time Clio OAuth in the browser; add --manual to paste the redirect URL
python -m app.cli sync        # pull the matter's records and documents from Clio (GET only)
python -m app.cli digest      # pages -> facts -> brief; model results are cached by input hash
uvicorn app.main:app --port 8000
pytest -q
```

```bash
# frontend (from frontend/)
npm install
npm run dev                   # http://localhost:5173, proxies /api to port 8000
```

Open `http://localhost:5173/matters/<clio matter id>`. The Share button in the Providers panel creates a provider link at `/p/<token>`.

`python -m app.cli seed-dev` loads an invented matter for development and tests without Clio. The demo runs on a live sync of the real matter. `python -m app.cli reset` deletes the database and every downloaded file.

## Architecture

```
Clio Manage (read-only, API v4)
   -> sync          backend/app/clio/      every record and document of one matter, with ETags
   -> digest        backend/app/digest/    code-only facts from structured records; a vision model per PDF page
                                           and per note or email; verification; a merge model for roles,
                                           significance, and the brief
   -> fact store    SQLite                 one row per claim, each with its source, page, and verbatim quote
   -> API           backend/app/api/       firm routes, and provider routes behind a default-deny filter
   -> firm view     /matters/:id           brief, KPIs, action board, ranked facts, providers, source drawer
   -> provider view /p/:token              status page scoped to one provider
```

One store of sourced facts feeds both views; the provider view is the same data behind a stricter filter. Model output is stored once and served from the database: no model runs when a page loads. Details are in `docs/architecture.md` and `docs/digest-pipeline.md`.

## How accuracy is handled

- **Every fact carries its source.** A fact stores its Clio record, and for documents its page number and a verbatim quote. A fact without them is not rendered. Each chip opens the note or email with the quote highlighted, or the PDF page with the quote above it.
- **Quotes are checked.** A model-extracted fact whose quote does not appear in the input text is dropped.
- **Money and dates on scans are read twice.** If the two reads disagree, the fact is kept at low confidence with both values. When sources disagree on a KPI, the strip shows every value and says so.
- **Uncertainty is visible.** Low-confidence facts have a dashed source chip. A KPI with no supporting fact says "Not found in file" instead of a number.
- **Nothing case-specific is in the code.** Custom fields and contact roles are mapped to canonical slots by a cached model call, so the pipeline runs on any matter ID.

## How sharing is enforced

The provider boundary is one function, `visible_facts_for_share` in `backend/app/services/visibility.py`, and every provider response is built from its output in `backend/app/services/provider_view.py`. The browser never receives a fact the provider may not see.

- **Default-deny.** A fact is released only when an enabled setting names its kind, it concerns this provider where the setting requires that, it is not flagged as strategy, the firm has not hidden it, and the link is neither expired nor revoked. Case value, liability, negotiations, expenses, and client contact have no setting that can release them.
- **Neutral wording.** Case-level sections carry labels written in code or as neutral status text, never a model-written title that could paraphrase an internal note. A provider can open only the cited page of their own bill or record.
- **The preview is the payload.** The share composer's preview and the provider's link call the same function, and a test checks that a created link returns exactly what was previewed.
- **The link is the credential.** A 32-byte random token that expires (30 days by default) and can be withdrawn. An expired or withdrawn link returns 410 with no data. The firm sees when each link was opened.
- **Tested.** `backend/tests/test_visibility.py` covers internal kinds, another provider's bills, sections turned off, hidden items, expired and revoked links, and another matter's facts. The tests were confirmed to fail when the filter is broken.

## What is stubbed

- **No real authentication for firm users.** Seeded stub accounts and a header-based user switcher stand in for logins. Provider access is by unguessable link only; there is no provider login.
- **Clio's personal-injury endpoints are not synced.** Bills come from documents, notes, and the expense ledger, not from `/medical_records_details.json` or `/damages.json`.
- **Calendar entries all become deadlines,** including treatment appointments. Time entries produce no facts; firm spend counts non-time entries only.
- **The firm's name is not shown on the provider page,** because no synced record carries it.
- **A live link cannot be edited.** To change what a provider sees, withdraw the link and share again.
- **`cli seed-dev` loads an invented matter** (`backend/tests/fixtures/synthetic_matter.py`) for development and tests, including a handwritten brief. The demo runs on a live sync.

The full lists are in `docs/progress.md` and the track files in `docs/tracks/`.
