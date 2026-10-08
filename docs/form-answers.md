# Submission form answers (draft)

Fill every bracket from the running system before submitting. Do not invent numbers: the cost comes from `GET /api/ops/cost` after a full digest of the real matter.

## 1. GitHub repository

https://github.com/aokhader/Clarity (the trial's work is on branch `kit-trial`). Team size: 2.

## 2. 90-second clip

**[MANAGER: Google Drive link, public access. Not in the repository.]** Script: `docs/submission.md`.

## 3. Tech stack

FastAPI and SQLite backend, Vite and React frontend, running on localhost. Clio Manage is read through API v4 with GET requests only; the client raises on any other method. All derived data (facts, digests, shares, view history) lives in a local SQLite file outside Clio.

## 4. Models and cost

Per-page and per-record extraction: `claude-haiku-5-5`. Field and role mapping, significance, and the brief: `claude-sonnet-5-5`. These are the models since 2026-10-08 (D36).

**A whole case on these models: about $1.40. This is an estimate, not a measurement:** no full digest has run on them. It prices the measured October 2 digest's tokens at their rates:
- extraction, about $0.48 to $0.54. On the same records, Haiku used 1.1 times the input and 2.2 to 2.5 times the output tokens of the October 2 model. The ratio comes from records only, and most extraction calls read scanned pages.
- the merge, about $0.89, assuming Sonnet uses as many tokens as the October 2 model did.

**Measured: one full digest on October 2 cost $7.65,** on `claude-sonnet-5-5` for extraction and `claude-opus-5-5` for the merge:
- 361 pages and 112 records;
- 514 model calls: 473 extraction calls ($5.86) and 41 merge calls ($1.79);
- 1,728,515 input and 329,989 output tokens.

This was measured from `GET /api/ops/cost` and the `llm_calls` table. A further 184 calls were rejected by the API and cost nothing.

**Measured: the two update runs on 2026-10-08 cost $0.17 together,** on the D36 models. They re-ran only the calls whose prompts or inputs had changed, so they price an update, not a whole case.
- The re-digest made 6 calls (36,295 input and 7,905 output tokens), for $0.0979.
- The re-read of 9 records made 10 paid calls, and answered 4 more from the cache (49,274 input and 15,266 output tokens), for $0.0760.
- No call failed. A trial on a copy of the database before them made 6 calls for $0.0148.

Gemini's free tier was tried first (D30, D31) and dropped: it answered 4 of 14 attempts in a 2026-10-08 trial (D36).

Reopening the matter costs $0, because results are stored and cached by input hash. A second digest over unchanged inputs makes no model call (`backend/tests/test_pipeline_second_digest.py`).

## 5. Anything the judges should know

**Differentiator.** Every sentence, date, and amount on screen links to the note, email, or PDF page it came from. The provider view is the same sourced data behind a default-deny filter the attorney controls, with a preview that is exactly what the provider receives. Before anything is sent to a provider, a draft checker tests each amount and date against the file. It locks a sentence that would disclose an internal figure, and says when a date is in the file but not on that provider's link.

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
- No full digest has run on the current models. The whole-case figure for them is an estimate.
- Another party's liability policy (the defense driver's own auto policy) is labelled "Client's other policy" on the firm's Coverage tile. The policy field has no value for another party's liability. Providers never see it, since a link releases only the defendant's limits.
- A share stores hidden items by fact id. A re-digest that re-reads a record gives its facts new ids, so an item hidden on a share would come back. No share exists on the real matter. This is a gap in the provider boundary, to fix after the freeze.
- The brief rewritten on 2026-10-08 is accurate, but it leaves out the defense medical exam findings and the pleaded limitations defense. What matters, the ranked feed on For Attorney, still shows both.
- Call notes have not been made by a live model on the real matter. A stored call does not record which firm user confirmed consent.
- A provider link's "shared on" and "expires" dates are UTC days.
- Pages read before a provider was known never get that provider.
- The screenshots show the invented `seed-dev` matter, not the real one (D33).
- The full list, with the files where each item lives: README, "Half-done or stubbed".

## 6. Live link or install path

Localhost only. Install and run steps are in `README.md`.
