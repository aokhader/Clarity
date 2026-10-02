# Submission

Deadline: form in and all committed work done by 4:00 PM PT. Submission order is presentation order, so earlier is better.

## What the form asks for

1. **GitHub repository.** The repository is the submission. Screeners verify features and code from it.
2. **A 90-second clip** on the Sapini matter, as a Google Drive link with public access.
3. **Tech stack:** built with, running on, and where data lives outside Clio.
4. **Which models run the digestion,** and the approximate cost to run one case.
5. **Anything the judges should know:** what we are proud of, the differentiator, where to look first, and anything half-done or hardcoded.
6. **Optional:** a live link or install path.

Also state the team size on the form.

## Answer templates

Fill the brackets from the running system. Do not invent numbers.

**Stack.** FastAPI and SQLite backend, Vite and React frontend, running on localhost. Clio Manage is read through API v4 with GET requests only. All derived data (facts, digests, shares, view history) lives in a local SQLite file outside Clio.

**Models and cost.** Per-page and per-record extraction: [EXTRACT_MODEL]. Merge, scoring, and brief: [MERGE_MODEL]. One full digest of the Sapini matter: [N] pages, [N] model calls, about $[X]. Re-opening the matter costs $0 because results are cached; a re-sync digests only changed records.

**Where to look first.**
- `backend/app/digest/` for the pipeline: page-level extraction with verbatim quotes, verification, then a merge step that only sees extracted facts
- `backend/app/api/provider.py` and `visible_facts_for_share` for the server-side sharing boundary, with tests
- `backend/app/clio/client.py` for the GET-only client

**Differentiator.** Every sentence, date, and amount on screen links to the note, email, or PDF page it came from, and the provider view is the same sourced data behind a default-deny filter the attorney controls.

**Half-done or hardcoded.** Copy the "Stubs and shortcuts" and "Known issues" sections of `docs/progress.md` as they stand at submission.

## README outline

1. One-paragraph description and a screenshot of each view
2. Quick start: environment variables, `cli auth`, `cli sync`, `cli digest`, run both servers
3. Architecture in ten lines, with a pointer to `docs/architecture.md`
4. How accuracy is handled: quotes, verification, confidence flags
5. How sharing is enforced
6. What is stubbed

## The 90-second clip

Record at 1440 by 900 with the browser zoomed so the brief is readable on a projector. Rehearse once before recording.

| Time | Show |
|---|---|
| 0:00 to 0:10 | The problem in one sentence over the Clio matter's tabs |
| 0:10 to 0:35 | Open the matter in the firm view: photo, stage, KPI strip, brief |
| 0:35 to 0:50 | Click a date in the brief; the drawer opens the scanned page with the quote |
| 0:50 to 1:00 | Since-you-last-opened and the action board |
| 1:00 to 1:20 | Share with a provider: toggle one section off in the composer, copy the link, open the provider view, show it is absent |
| 1:20 to 1:30 | Back in the firm view, the share shows as opened. Close on cost per case. |

## The 4-minute pitch (if we reach the top 7)

The pitch is delivered over the video to trial attorneys and AI builders.

1. The attorney's question: "what's been happening on this case?" (20 seconds)
2. The firm view on Sapini, led by the brief and click-to-source (90 seconds)
3. The provider view and the sharing line the attorney controls (60 seconds)
4. How it stays accurate and what it costs per case (40 seconds)
5. What we would build next (30 seconds)

Lead with what the attorneys in the room can check against their own experience. Leave the stack for questions.
