# Submission form answers (draft)

Fill every bracket from the running system before submitting. Do not invent numbers: the cost comes from `GET /api/ops/cost` after a full digest of the real matter.

## 1. GitHub repository

[repository URL]. Team size: [N].

## 2. 90-second clip

[Google Drive link, public access]. Script: `docs/submission.md`.

## 3. Tech stack

FastAPI and SQLite backend, Vite and React frontend, running on localhost. Clio Manage is read through API v4 with GET requests only; the client raises on any other method. All derived data (facts, digests, shares, view history) lives in a local SQLite file outside Clio.

## 4. Models and cost

Per-page and per-record extraction: [EXTRACT_MODEL]. Field and role mapping, significance, and the brief: [MERGE_MODEL]. One full digest of the matter: [N] pages, [N] model calls, about $[X]. Reopening the matter costs $0 because results are stored and cached by input hash; a re-sync digests only changed records.

## 5. Anything the judges should know

**Differentiator.** Every sentence, date, and amount on screen links to the note, email, or PDF page it came from. The provider view is the same sourced data behind a default-deny filter the attorney controls, with a preview that is exactly what the provider receives.

**Where to look first.**
- `backend/app/digest/`: page-level extraction with verbatim quotes, verification (quote check, second read on scans), then a merge step that sees only extracted facts
- `backend/app/services/visibility.py` (`visible_facts_for_share`) and `backend/app/services/provider_view.py`: the server-side sharing boundary, with `backend/tests/test_visibility.py` and `backend/tests/test_share_api.py`
- `backend/app/clio/client.py`: the GET-only Clio client

**Half-done or hardcoded.**
- No real authentication for firm users: seeded stub accounts and a header-based user switcher. Provider access is by unguessable, expiring link only; there is no provider login.
- `cli seed-dev` loads an invented matter for development and tests, including a handwritten brief (`backend/tests/fixtures/synthetic_matter.py`). The demo runs on a live Clio sync.
- Clio's personal-injury endpoints (`/medical_records_details.json`, `/damages.json`) are not synced; bills come from documents, notes, and the expense ledger.
- Calendar entries all become deadlines, including treatment appointments. Time entries produce no facts; firm spend counts non-time entries only.
- If Clio rejects a field name, a request falls back to a smaller field list.
- Deduplication deletes duplicate facts, so a source with a duplicate gets new fact ids on the next run.
- The provider page does not show the firm's name; no synced record carries it.
- A live provider link cannot be edited; the firm withdraws it and shares again.
- [Add anything left in the Stubs and Known issues sections of `docs/progress.md` and `docs/tracks/` at submission.]

## 6. Live link or install path

Localhost only. Install and run steps are in `README.md`.
