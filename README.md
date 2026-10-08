# Clarity

Clarity turns one personal-injury matter in Clio Manage into two views. The firm gets a brief it can read in 90 seconds: the case in sentences, the figures that matter, what is overdue, and what changed since the last visit. The medical providers treating the client on lien get a private link that shows only what the attorney releases: where the case stands, whether coverage is confirmed, what the firm needs from them, and their own bills and records. Every date, amount and claim on screen opens the note, email or PDF page it came from, with the quote highlighted. Two tools sit on the same fact store: a draft checker that tests each amount and date in a message to a provider against the file, and locks a sentence that would disclose an internal figure; and a Calls view that lists who to call next and turns a call's transcript into notes, each citing the words it came from. Clio is read with GET requests only, and nothing is ever written back. Models run when the matter is digested, and when the firm asks for a call's notes. They never run when a page loads, and each result is stored and reused.

Built for the Swans Applied AI Hackathon (Law-Di-Gras, San Diego, October 2, 2026), then finished in a trial run by a team of agents (see [The trial](#the-trial)).

| Case Overview | For Attorney |
|---|---|
| ![Case Overview: the brief, with a source chip on each sentence](docs/screenshots/overview.png) | ![For Attorney: KPI tiles, action board, ranked facts, providers](docs/screenshots/attorney.png) |
| **For Service Provider (the firm's preview)** | **Calls** |
| ![The firm's preview of a provider's link](docs/screenshots/provider-preview.png) | ![Calls: who to call next, and the consent step before transcription](docs/screenshots/calls.png) |
| **The provider's own page** | **The draft checker, in the share composer** |
| ![The provider page at /p/token: the provider's own bills, with a lien labelled and kept out of the total](docs/screenshots/provider-page.png) | ![A note to a provider: its bill total supported with a chip, an internal figure locked as Don't send](docs/screenshots/draft-check.png) |

The screenshots show the invented matter that `cli seed-dev` loads, never the real one: a screenshot of the real matter would commit a real person's medical details (D33).

## Run it

You need Python 3.11 or later, Node 20 or later, and Git. Clarity runs on localhost: the API on port 8000, the web app on port 5173.

### Without Clio: the invented matter

This is the path a clean clone takes. It needs no Clio account and no model key.

**macOS or Linux**

```bash
git clone --branch kit-trial https://github.com/aokhader/Clarity.git && cd Clarity
cp .env.example .env

cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.cli seed-dev        # loads the invented matter as matter 1
uvicorn app.main:app --port 8000  # leave running; use a second terminal for the rest
```

```bash
cd Clarity/frontend
npm install
npm run dev                       # http://localhost:5173, forwards /api to port 8000
```

**Windows (PowerShell)**

```powershell
git clone --branch kit-trial https://github.com/aokhader/Clarity.git; cd Clarity
Copy-Item .env.example .env

cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1        # in Git Bash: source .venv/Scripts/activate
pip install -r requirements.txt
python -m app.cli seed-dev
uvicorn app.main:app --port 8000
```

```powershell
cd Clarity\frontend
npm install
npm run dev
```

If PowerShell refuses to run `Activate.ps1`, skip activation and call the environment's Python directly, such as `.venv\Scripts\python -m pip install -r requirements.txt`.

Open `http://localhost:5173/`. It lists the matters; the invented one is at `/matters/1`. The views are in the left rail. To make a provider link, open **For Attorney** and use **Share** in the Providers panel. The link opens at `/p/<token>`.

**Measured on a clean clone** of commit `189e7ec` on Windows 11 (Git Bash), with Python 3.14.8 and Node 22.23.1, on 2026-10-07.
- PowerShell was used only to check that `Activate.ps1` works.
- pip and npm had packages cached from earlier installs on that machine, so a first install elsewhere will take longer.
- The clone came from a local disk, not GitHub.
- The macOS and Linux commands were not run.

| Step | Time |
|---|---|
| `python -m venv .venv` | 12.9 s |
| `pip install -r requirements.txt` | 37.0 s |
| `python -m app.cli seed-dev` | 2.5 s |
| `npm install` | 21.8 s |
| `npm run dev`, until Vite is ready | 1.3 s |
| The steps above together, until the page is served | about 76 s |
| `pytest -q` (341 passed) | 63.4 s |
| `bash scripts/check.sh` | 67.9 s |

On the invented matter, with no model configured, each matter route called in the clean clone answered in under 35 ms: the header, brief, feed, actions, providers, injuries, timeline, changes, shares, calls and a fact's source. `npm install` reports 7 high-severity advisories, all in the dependency tree of the `shadcn` package; see [Half-done or stubbed](#half-done-or-stubbed).

### With Clio: a real matter

Fill `.env` at the repository root. Every setting, with its default, is in `backend/app/config.py`.

- **Clio:** a developer application with read permissions (`CLIO_CLIENT_ID`, `CLIO_CLIENT_SECRET`). Register `http://127.0.0.1:8000/oauth/callback` as its redirect URI. `CLIO_MATTER_QUERY` is the search string that finds the matter.
- **Models:**
  - `LLM_PROVIDER` is `anthropic`, `openai` or `gemini`. The trial's runs used `anthropic`, with `claude-haiku-5-5` for extraction and `claude-sonnet-5-5` for the merge (D36). The October 2 digest used `claude-sonnet-5-5` and `claude-opus-5-5`.
  - `LLM_API_KEY`, `EXTRACT_MODEL` (vision-capable, one call per page or record) and `MERGE_MODEL` (mapping, significance and the brief).
  - The four `*_PRICE_*` settings, in USD per million tokens, so the cost can be computed.
  - `EXTRACT_RPM` and `MERGE_RPM` cap and space the requests per minute to each model (D31). `LLM_MAX_RETRY_WAIT_SECONDS` fails a call at once when the API asks for a longer wait; retry it later.

Then, from `backend/` with the environment active:

```bash
python -m app.cli auth      # once: prints Clio's sign-in URL and waits for the redirect
python -m app.cli sync      # pulls the matter's records and documents (GET only)
python -m app.cli digest    # pages -> facts -> brief; each model result is stored and reused
uvicorn app.main:app --port 8000
```

- **Auth** listens on port 8000 for Clio's redirect, so stop the API server first. `auth --manual` lets you paste the redirect URL instead.
- **The one non-GET request** this project sends to Clio is OAuth's token exchange, which touches no case data.
- **Other commands:**
  - `cli digest --retry-failed` retries model calls that failed.
  - `cli digest --pages-only` renders pages without calling a model.
  - `cli reextract --dry-run` prices a re-read of chosen pages before running it.
  - `cli reset` deletes the database and every downloaded file.

Without credentials, each command stops with a message, as seen in the clean clone:
- `auth` names the missing `CLIO_CLIENT_ID` and `CLIO_CLIENT_SECRET`.
- `sync` says "No Clio token stored".
- `digest` builds the facts that need no model, then says "Set EXTRACT_MODEL and MERGE_MODEL in .env".

### Checks

`bash scripts/check.sh`, from the repository root (Git Bash on Windows), runs what a screener would:
- ruff
- the Clio client's GET-only tests
- a scan for case data
- a scan for private files
- the backend tests
- the strict TypeScript check

Each step prints ok, FAIL or SKIPPED, and SKIPPED means the step verified nothing. The case-data step derives its forbidden terms from the synced matter in `data/app.db`. On a clone holding only the invented matter, it reports SKIPPED and says why.

## What works

### Verified

Seen working on the hackathon's matter, and by whom.

- **By the lead, in the browser, during the trial (2026-10-07):**
  - The brief's sentences, each ending in source chips that open the cited page (U1). That was the October 2 brief; the model runs of 2026-10-08 rewrote it (below).
  - The source drawer, and the share preview's chips, which open their sources (U8).
  - The draft checker:
    - in the composer: the "don't send" lock, and removing a sentence (U4);
    - the brief's "differs from the file" mark (U7).
  - "No bills on file" in place of $0, and the Coverage tile's leading limit with the client's own policies labelled beneath it (U9). That was before the limits were re-read; the tile has changed since (see Known issues).
  - Calls:
    - the list of whom to call, with chips;
    - a typed number;
    - the consent gate;
    - the notes state when no model is configured.
- **After the model runs of 2026-10-08 (D36; costs under [Cost per case](#cost-per-case)):**
  - The lead checked the results in the browser after both runs.
  - The reviewer checked them through the API, with the database opened read-only, at `f37a110`:
    - The brief has 5 sentences, down from 8, and every one cites facts. Its headline cites 4 facts (D14).
    - No sentence or headline figure is marked "differs from the file" or "not in the file". Two sentences state no amount or date, so they are "unchecked".
    - No open question asks for a date the header already shows (P11).
    - The stage label has no trailing space, and the ledger's medical charges carry the neutral title (P12).
    - 19 of the 20 policy limits name their policy (D19).
    - Economic damages and recovery caps are kinds of their own (D20), and the Case value and Medical specials tiles cite neither.
    - Each provider's bill facts are unchanged by the runs: the same amounts, sources and pages as in the backup taken before them. So every provider's total is unchanged.
  - The critic's third pass, over the rewritten brief and the re-read limits, is under way (C3).
- **After the re-sync of 2026-10-07 (D30), seen by the reviewer through the API on 2026-10-08:**
  - The sync fetched again the one pleading whose download had failed on October 2, and the next digest rendered it. All 27 of its page images now load.
  - All 31 documents carry Clio's received date, which the source drawer shows as the document's own date.
- **By the lead, outside the browser:**
  - The draft checker's server side on the real matter (B1).
  - The in-place schema upgrade on the real database, with all 14 tables keeping their row counts (D24).
- **By the critic, through the API with the database opened read-only, in two passes** (at commits `9c05e39` and `c18388b`; `docs/reviews/critic.md`):
  - All ten providers were previewed with every setting on, and no internal or strategy-flagged fact reached a payload.
  - The firm view's update text for all ten providers came back supported from the draft checker, with no false lock.
  - The provider routes are three GETs.
  - No GET request reaches a model. Every firm route answered in 0.2 to 0.35 s with no model configured.

### Seen working in a clean clone

By the reviewer, on the invented matter, on 2026-10-07:
- The steps under [Without Clio](#without-clio-the-invented-matter), in Git Bash on Windows, and `sync` and `digest` with no credentials.
- `pytest`: 341 passed at `189e7ec`. In the main checkout, 371 pass at `f37a110`, through `check.sh` on 2026-10-08.
- `check.sh`: no step failed after `e22a5ae`. Before that commit, the case-data step failed falsely on the invented matter's own fixture.
- Sharing:
  - A created link returns exactly what the preview showed.
  - A withdrawn link returns 410.
  - Five deliberate breaks of the provider filter in `services/visibility.py` were tried: the expiry and withdrawal check, another provider's bills, hidden items, strategy flags, and the shareable tag. Each one made the visibility and share tests fail.
- The draft checker:
  - A sentence restating a provider's own bill total is `supported`.
  - A figure held only in an internal note is `do_not_send`, with "Kept internal: never shared with providers" and a chip to that note.
  - An unknown date is `not_in_file`.
  - The server refuses a share whose note holds the internal figure (422) and accepts one that does not (201).
- After D35's backend change (`01d6e41`), a live link served each item in its bills list as a bill or a lien.

By the lead, in the browser, on the clean clone's invented matter, while taking the screenshots above:
- The freeze fixes `b71b281`, `1b5c369` and `cfc121b` (D35):
  - the Case value range fits its tile, breaking after its dash;
  - on the provider page and the firm's preview, the list reads "Bills and liens", with a caption that liens are not added to the total;
  - each lien row is labelled "Lien", with its amount set apart from the bills.
- The other shots: the brief's chips, the consent step, and the draft checker's lock in the share composer.

### Built, lightly tested

Unit tests pass. None of these has been seen in the browser on the real matter since it was last changed.

- **Liens in the provider update (D35, `612945b`):** the "Send update" draft counts and totals bills only, and lists liens under a heading of their own. On the real matter no lien reaches a provider; see Known issues.

- **Draft-checker matching (D25, D28):**
  - It reads amounts written with k, grand, bucks, USD, a trailing or full-width dollar sign, or in words, plus bare figures of four or more digits.
  - It catches ranges, rounding, and an internal figure split across two amounts.
  - It counts the firm-spend total and call-note figures as internal.
  - A date locks only when it is the date of a sensitive internal fact (an offer, a demand, a settlement, a valuation, a limit) or of a legal deadline. A plain calendar entry does not lock.
- **Fixes since the critic's second pass:**
  - The Case value tile leads with the firm's own valuation.
  - A provider's "last movement" is left out when the latest change has no date.
  - The client's treating injuries are listed first.
  - The consent wording names every service the audio and transcript reach (D27).
- **Pipeline fixes (P2 to P7).** The re-sync and the two model runs on the real matter went through them with no failed item, so their failure paths were not exercised there.
  - A partly failed sync is pulled again (P2).
  - A sync stopped by any error is closed as failed (P3).
  - A failed mapping call keeps the previous mapping (P4).
  - The policy-limit cross-check (P5).
  - A second digest over unchanged inputs calls no model (P6). In run (b), the unchanged mapping calls and one record were answered from the cache.
- **Model access:**
  - The Gemini provider (D30) and its per-model request limit (D31). On the free tier, the trials got no answer in 12 attempts on 2026-10-07 (D34) and 4 answers in 14 attempts on 2026-10-08 (D36). So the runs moved to Anthropic, and no digest of the real matter has run on Gemini.
  - The "Retry failed calls" control (D29), which had not been clicked by the freeze. The runs had no failed call to retry.
- **Call notes from a transcript (C-P):** every note's quote is checked against the transcript. The real matter's database holds no notes made by a live model, and the Manager's test call (C-T) has not happened.

### Half-done or stubbed

From the stubs list in `STATUS.md`, the track files in `docs/tracks/`, `docs/progress.md`, and the critic's open findings.

**Stubs and shortcuts**
- **Firm users:**
  - No real authentication. Seeded stub users (Demo Attorney, Demo Paralegal, Demo Case Manager) are chosen with a header switcher (`backend/app/services/users.py`, `frontend/src/components/firm/UserSwitcher.tsx`).
  - Each stub user's first "last opened" date is seeded: 21 days ago, 7 days ago, and never (`backend/app/services/visits.py`).
- **Providers:**
  - Provider access is by an unguessable, expiring link only; there is no provider login.
  - "Send update" leaves the recipient blank, because no synced field holds the provider's email (`frontend/src/components/share/SendUpdateMenu.tsx`).
- **`cli seed-dev`** loads an invented matter for development, tests and the screenshots, including a handwritten brief (`backend/tests/fixtures/synthetic_matter.py`).
- **What the sync and digest leave out:**
  - Clio's personal-injury endpoints (`/medical_records_details.json`, `/damages.json`) are not synced. Bills come from documents, notes and the expense ledger.
  - A Clio request falls back to a smaller field list if Clio rejects a field name.
  - Calendar entries all become deadlines, including treatment appointments. Only legal deadlines lock a draft (D28).
  - Time entries produce no facts, and firm spend counts non-time entries only.
- **The draft checker:**
  - It checks figures only. A sentence that discloses an internal fact without an amount or a date is `unchecked`, and the UI says so (D17).
  - A figure near an internal amount, but not equal to it, rounded to it, or in a range around it, is not flagged.
- **Pipeline:**
  - A sync or digest that fails before its run row exists is held in server memory, so a restart forgets it (`backend/app/services/jobs.py`).
  - A failed model call is not retried until `cli digest --retry-failed` or the footer's retry control (`backend/app/digest/llm.py`).
  - `cli reextract --dry-run` prices a selection from the average recorded cost per call, which is an upper bound (`backend/app/digest/reextract.py`).
  - A date said on a call without a year is placed at the nearest such day within six months, else left out (`backend/app/digest/call_notes.py`).
- **Page and link details:**
  - The provider page does not show the firm's name; no synced record carries it.
  - A live link cannot be edited. To change what a provider sees, withdraw it and share again.
  - The `requests` setting releases only open record requests and open tasks.

**Known issues**

The issues that waited on the re-digest, the re-read and the re-sync are resolved: the brief's unsourced figure, the headline without chips, the open question about a date on the page, the ledger bill's raw title, the missing pleading and the upload dates. Policy limits are now tagged by policy, all but one. What was seen is under [Verified](#verified). These remain:

- **The Coverage tile warns "Sources disagree" again, since the re-read.**
  - One of the 20 limits names no policy, and one of the defendant's limits names neither per person nor per occurrence. The tile counts each as possibly the same limit as a different figure.
  - So its nine figures are listed as equals under the warning, and the defendant's limit no longer leads (`backend/app/services/kpis.py`, `_coverage`).
  - Seen through the API's `sources_disagree` flag and read from the tile's code; the critic's third pass is checking the limits.
- **No full digest has run on the D36 models.** The whole-case cost at those models is an estimate; see [Cost per case](#cost-per-case).
- **Pages read before a provider was known never get that provider.** Two fixes are written up in `STATUS.md`; neither is built.
  - None of the real matter's 8 lien facts has a provider attached, as found during D35 and confirmed in the database.
  - A link's bills-and-liens setting releases only its own provider's facts, so no provider's link shows a lien on the real matter.
- **On the provider page and in the firm's lists:**
  - The "shared on" and "expires" dates are UTC days, so a link made in the evening, Pacific time, reads as made the next day (`backend/app/services/provider_view.py`).
  - A stored call records the consent wording but not which firm user confirmed it.
  - As of the critic's second pass:
    - the provider's "File opened" date (from a note) and the header's opened date (from Clio) differ by two days;
    - "Waiting on others" lists 45 items, 26 of them undated.
- **Smaller issues:**
  - Deduplication deletes duplicate facts, so a source that had one gets new fact ids on the next run.
  - A re-sync pulls the matter named by `CLIO_MATTER_QUERY`, not necessarily the one on screen.
  - Each visit uses up the "since you last opened" block.
  - The stored brief's `generated_at` still reads its first generation on October 2, though the runs rewrote its text on 2026-10-08. `f37a110` dates each later rewrite correctly, but this brief was written before it. The screen does not show this date.
- **Tooling:**
  - `npm install` reports 7 high-severity advisories, all in the dependency tree of `shadcn`, whose stylesheet the app imports. They have not been triaged.
  - On Windows, `uvicorn --reload` sometimes keeps serving old code; restart it if a new route returns 404.
  - The Vite proxy target is fixed at port 8000 (`frontend/vite.config.ts`).
  - `cli reset` refuses to delete a data directory that holds anything it does not expect, including the backups that `upgrade_schema` makes.

## Cost per case

Measured with `GET /api/ops/cost` and the `llm_calls` table, on the hackathon's matter. Every call is costed at the prices set in `.env` when it ran.

**One full digest, measured on October 2, 2026:**

| | Model | Calls | Cost |
|---|---|---|---|
| Extraction: one call per page or record (361 pages in 31 documents, 112 records) | `claude-sonnet-5-5` | 473 | $5.86 |
| Merge: field and role mapping, significance, the brief | `claude-opus-5-5` | 41 | $1.79 |
| **One full digest** | | **514** | **$7.65** |

That is 1,728,515 input and 329,989 output tokens. Another 184 calls were rejected by the API (HTTP 400 or 401), and they used no tokens and cost nothing.
- **Reopening the matter costs nothing,** because no page load calls a model.
- **A second digest over unchanged inputs makes no model call,** because results are cached by input hash (`backend/tests/test_pipeline_second_digest.py`).

**The trial's model runs, measured on 2026-10-08 (D36).** These ran on Anthropic's paid tier:
- extraction on `claude-haiku-5-5`, at $0.10 per million input tokens and $0.50 per million output tokens;
- the merge on `claude-sonnet-5-5`, at $2 and $10.

They re-ran only the calls whose prompts or inputs had changed, so they price an update, not a whole case. Run (a) re-digested the matter. Run (b) re-read 9 named records under the new extraction prompt (P13).

| Run | Purpose | Model | Tokens in / out | Cost |
|---|---|---|---|---|
| (a) | Role mapping | `claude-sonnet-5-5` | 1,785 / 368 | $0.0073 |
| (a) | Field mapping | `claude-sonnet-5-5` | 2,311 / 378 | $0.0084 |
| (a) | Ledger classification | `claude-sonnet-5-5` | 3,742 / 737 | $0.0149 |
| (a) | The matter's record | `claude-haiku-5-5` | 3,503 / 4,961 | $0.0028 |
| (a) | Significance | `claude-sonnet-5-5` | 5,890 / 798 | $0.0198 |
| (a) | The brief | `claude-sonnet-5-5` | 19,064 / 663 | $0.0448 |
| (b) | 8 records re-read | `claude-haiku-5-5` | 23,507 / 13,744 | $0.0092 |
| (b) | Significance | `claude-sonnet-5-5` | 5,600 / 883 | $0.0200 |
| (b) | The brief | `claude-sonnet-5-5` | 20,167 / 639 | $0.0467 |

- **Run (a):** 6 calls, 36,295 input and 7,905 output tokens, $0.0979, and 38 s by its digest run's own record.
- **Run (b):** 10 paid calls and 4 answered from the cache (the three mapping calls and one record), 49,274 input and 15,266 output tokens, $0.0760, and 64 s.
- **Both runs:** 16 paid calls, $0.1738, against a $2 stop. No call failed.
  - Pipeline reports no retries and no 429s.
  - The trial on a copy of the database, just before the runs, made 6 calls, all answered on the first try, for $0.0148. That copy is not in `app.db`, so this figure is from pipeline's report.
- **`GET /api/ops/cost` now reports the matter's total:** 714 calls and 14 cache hits, 1,814,084 input and 353,160 output tokens, $7.83. That covers the October 2 digest, its 184 rejected calls, and the two runs.

**A whole case at the D36 models: about $1.40, an estimate, not measured.** No full digest has run on these models. The estimate prices the October 2 digest's tokens at the D36 rates:
- **Extraction, about $0.48 to $0.54.** The October 2 extraction used 1,481,705 input and 289,882 output tokens. On the same records, Haiku used 1.1 times the input and 2.2 to 2.5 times the output of the October 2 Sonnet calls (2.2 in pipeline's trial, 2.5 over the 9 records in the runs). The ratio was measured on records only, and most extraction calls read scanned pages.
- **The merge, about $0.89.** On October 2 it used 246,810 input and 40,107 output tokens on Opus. These are priced at Sonnet's rates, assuming Sonnet uses as many tokens.

## Where data lives

Everything Clarity derives stays on the machine that runs it. Nothing is written to Clio.

- **`data/`**, at the repository root, is gitignored. `DATA_DIR` in `.env` moves it.
  - **`app.db`**, SQLite, holds:
    - the synced Clio records, with their ETags;
    - page text;
    - every fact, with its source, page and verbatim quote;
    - the brief;
    - every model call, with its tokens, cost and cached response;
    - provider links and their opens, the stub users and their visits;
    - calls, transcripts and notes;
    - sync and digest runs;
    - Clio's OAuth tokens.
  - **`files/`** holds the downloaded documents, and **`pages/`** the rendered page images.
  - **`app.db.bak-<time>`** is the copy `upgrade_schema` takes before upgrading the database in place (D24). The copies taken by hand before each model run (D36) carry the same name.
  - **`raw-export.json`** exists only while `check.sh` runs its case-data step.
- **`.env`**, at the repository root, holds the Clio credentials and the model key. It is never committed.
- **Outside the machine:**
  - The model provider receives page images and record text during a digest, and a call's transcript when notes are requested. That was Anthropic for the October 2 digest and the trial's runs (D36).
  - The Gemini trials on copies of the real matter's database (D34, D36) sent some of its content to Google's free tier, whose terms allow Google to use it. D36 stopped this.
  - On a call, Chrome's speech recognition sends the microphone audio to Google's speech service. The consent step says so (D27).

## Repository map

```
backend/app/
  main.py, config.py, db.py, models.py, schemas.py   app, settings (the only reader of the environment), tables, API contract
  cli.py                     auth, sync, digest, reextract, seed-dev, reset
  clio/                      GET-only Clio client, OAuth, sync with ETags
  digest/                    pages -> facts -> brief
    pages.py, structured.py  PDF pages (PyMuPDF), and facts read from structured records in code
    extract.py, verify.py    one model call per page or record; a quote that is not in the input is dropped; money and dates on scans are read twice
    mapping.py, matter_fields.py, ledger.py   custom fields and contact roles mapped to canonical slots, so no matter's labels are in code
    merge.py, brief.py, cross_check.py        significance, the brief, and the specials and policy-limit cross-checks
    call_notes.py            notes from a call transcript, each quoting it
    llm.py                   every model call: cached by input hash, costed, rate-limited
    prompts/                 versioned prompt files
  services/                  queries and rules behind the routes
    visibility.py            visible_facts_for_share: the provider boundary, default-deny
    provider_view.py         the provider payload, built only from that function's output
    draft_check.py, money_mentions.py, text_mentions.py, known_values.py   the draft checker
    brief_check.py           brief figures checked against today's facts when served (D12)
    kpis.py, providers.py, calls.py, ...
  api/                       thin routes: matters, facts, shares, provider, calls, ops
backend/tests/               371 tests; fixtures/synthetic_matter.py is the invented matter
frontend/src/
  api/                       types.ts mirrors schemas.py; TanStack Query hooks
  pages/, components/        firm views (firm/), provider link and composer (share/), calls/, shared/
  lib/                       formatting, labels, consent wording, speech transcript
scripts/check.sh             the screener's checks; export_raw.py feeds the case-data scan
tests/                       repository-wide Node tests: no case data, nothing private
docs/                        architecture, digest pipeline, Clio API notes, UI, briefs, reviews, track history
.claude/                     agent roles, path ownership and its hook (the trial)
```

`docs/architecture.md` and `docs/digest-pipeline.md` explain the design. The shortest route through the code is:
1. `backend/app/clio/client.py`
2. `backend/app/digest/extract.py` with `verify.py`
3. `backend/app/services/visibility.py` with `backend/tests/test_visibility.py`

## The trial

After the hackathon, Clarity was finished on the `kit-trial` branch by a team of Claude Code sessions, with one human as Manager making the product calls.
- **The lead** (a session with no role) kept the plan, integrated the work, ran the servers, and checked screens in the browser.
- **Six workers** each held one role: pipeline, backend (which also kept the API contract), ui-builder, researcher, critic and reviewer.
- **Ownership:** each role could edit only the paths `.claude/ownership.json` gives it, and a hook (`.claude/hooks/enforce-ownership.mjs`) refused anything else.

The shared memory is plain files:
- **`PLAN.md`:** backlog with owners, milestones, cut order and the trial's measures.
- **`STATUS.md`:** one row per role, plus the stubs list.
- **`DECISIONS.md`:** D1 to D36, each with its time and reason.
- **`docs/briefs/`:** the researcher's briefs.
- **`docs/reviews/critic.md`:** the critic's ranked findings.

The trial added the draft checker (D2) and Calls (D8). It fixed most of the Track A review's pipeline defects and of the critic's findings; the rest are listed under Half-done. Features were frozen at D32. The commits are `git log 987c1bf..kit-trial`.
