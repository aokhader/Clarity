# Submission form answers (draft)

Fill every bracket from the running system before submitting. Do not invent numbers: the cost comes from `GET /api/ops/cost` after a full digest of the real matter.

## 1. GitHub repository

https://github.com/aokhader/Clarity (the trial's work is on branch `kit-trial`, which is not yet on GitHub). Team size: **[LEAD: team size. Not measurable from the repository: its history shows two human commit authors.]**

## 2. 90-second clip

**[LEAD: Google Drive link, public access. Not in the repository.]** Script: `docs/submission.md`.

## 3. Tech stack

FastAPI and SQLite backend, Vite and React frontend, running on localhost. Clio Manage is read through API v4 with GET requests only; the client raises on any other method. All derived data (facts, digests, shares, view history) lives in a local SQLite file outside Clio.

## 4. Models and cost

Per-page and per-record extraction: `claude-sonnet-5-5`. Field and role mapping, significance, and the brief: `claude-opus-5-5`.

One full digest of the matter cost about $7.65:
- 361 pages and 112 records;
- 514 model calls: 473 extraction calls ($5.86) and 41 merge calls ($1.79);
- 1,728,515 input and 329,989 output tokens.

This was measured from `GET /api/ops/cost` and the `llm_calls` table for the October 2 digest. A further 184 calls were rejected by the API and cost nothing.

Reopening the matter costs $0, because results are stored and cached by input hash. A second digest over unchanged inputs makes no model call (`backend/tests/test_pipeline_second_digest.py`).

**[LEAD, after runs (a) and (b): the trial moved to `gemini-3.8-flash` for extraction and `gemini-3.7-flash` for the merge (D30, D31). Add their calls, tokens and cost from `GET /api/ops/cost`. Those runs re-run only changed prompts, so they price an update, not a whole case.]**

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
- The draft checker checks figures only. A sentence that discloses an internal fact without an amount or a date is `unchecked`, and a figure merely near an internal amount is not flagged.
- Several fixes take effect only at a re-digest, which has not run yet:
  - the headline's citations;
  - computed totals in the brief;
  - the new fact kinds;
  - which policy a limit belongs to.
  Until then, the stored brief from October 2 has one figure that no fact holds, and it is marked on screen.
- Call notes have not been made by a live model on the real matter. A stored call does not record which firm user confirmed consent.
- A provider link's "shared on" and "expires" dates are UTC days.
- Pages read before a provider was known never get that provider.
- One pleading's scan is missing on disk until a re-sync.
- The screenshots show the invented `seed-dev` matter, not the real one (D33).
- The full list, with the files where each item lives: README, "Half-done or stubbed".

## 6. Live link or install path

Localhost only. Install and run steps are in `README.md`.
