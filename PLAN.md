# Plan: the kit trial

Owned by the lead. Started 2026-10-06 on branch `kit-trial`. Times are relative to the kickoff (T+0:00); the lead writes the clock times in when the trial starts.

## Goal

Finish Clarity, and add one feature in the style of the podium team, using the hackathon kit: a lead, role-based worker sessions with owned paths, and STATUS/DECISIONS as shared memory. The second goal is to learn what the kit gets wrong, so record the trial measures below as you go.

## Decisions

Decided (details in DECISIONS.md):
- **D2:** the new feature is (a), the draft checker for provider updates. Amounts and dates in a provider update are checked in code against the fact store, and a sentence that would disclose an internal fact is locked with "don't send".
- **D3:** the brief's sentences come back with a source chip on each, for now. Expect a later revert to a clickable section that opens its documents.
- **D7:** rename every matter-derived term that steers a model, allowlist the generic rest, and remove real case data. The lead has done the allowlist and the doc fix; pipeline renames the two prompt terms (P8).

- **D8 to D11:**
  - Calls is built as (A): a hand-off call with your side transcribed; in-app two-sided calling (B) comes later.
  - Calls comes after the draft checker, and the freeze moves to T+6:00.
  - Workers run as background subagents of the lead.
  - The lead runs the dev servers.
- **D12 to D15:**
  - Brief figures are checked when served; a mismatch is marked "differs from the file" and shows today's figure.
  - One re-digest happens after pipeline's batch, once the Manager fills the model settings in `.env`, with a cost estimate first.
  - The brief headline cites its facts.
  - The Calls view accepts a typed number, stored only in Clarity.
- **D38 and D39 (2026-10-08, after the freeze):** one UI pass so the Overview answers, in 90 seconds, what the case is about, what has happened and where it is now. It uses the legal-memo restyle, margin citations, and moves the money tiles to the Overview. Three additive contract changes. No model call. Details are under "Overview pass".

Waiting for the Manager: nothing.

## Overview pass (D38, D39)

The Manager measured the Overview against CaseDesk and Corro.
- **What was wrong:** the first screen showed six metadata cards and pushed the story below the fold. There was no incident narrative and no chronology. The look was generic, against `docs/ui.md`.
- **The WCAG 2.2 audit:** a reflow blocker and five serious issues.
- **The target:** at least 9 of the 12 questions in `docs/ui.md` on the first screen at 1440×900, and all 12 within one scroll.

The design rules are in `docs/ui.md`.

The order:
1. Backend B11–B13 and ui-builder U10 run in parallel. U10 runs alone among ui-builder's items, since it touches every view.
2. Then U11–U17 and A11Y.
3. The lead checks the real matter (kind counts only) before U14 and U16 are accepted.

**Backend**
- [x] B11 `incident_account`. 30 min
  - In `services/incident.py`, choose among the **model** incident facts on the day `incident_fact()` picks: one with a description first, then by significance.
  - Never return the Clio field fact.
  - `MatterHeaderOut.incident_account` (`IncidentAccountOut {text, fact}`), committed with `types.ts`, and the frontend typecheck run (D23).
  - Add a code incident fact with no description to the fixture.
- [x] B12 `GET /matters/{id}/key-events?limit=10`. 60 min
  - `matter_key_events(session, matter_id, today, limit)`, built from:
    - the pinned header incident;
    - event kinds only: diagnosis, treatment visit, status change, coverage, demand, offer, settlement, records received, and past deadlines;
    - nothing after `today`;
    - restatements folded;
    - at most `KEY_EVENTS_PER_KIND = 3` per kind.
  - Returned oldest first.
  - Tests in `test_backend_key_events.py` with an explicit `today`.
- [x] B13 `SourceOut.pages` becomes `FirmPageOut(PageRef)` with `text` from `Page.text`. `ProviderSourceOut.page` stays `PageRef`. 20 min

**ui-builder**
- [x] U10 Tokens and the rail. 120 min
  - The paper, ivory, ink and ink-blue palette.
  - Every status token retuned to at least 4.5:1 for text and 3:1 for borders on every surface, with the ratios in a comment.
  - Corners of 8px or less, a solid `outline-ring`, and a reduced-motion rule.
  - `Panel` loses its icons and shadow.
  - A light 15rem rail.
  - No `slate-*`, `blue-*` or gradient classes left in the firm components.
- [x] U11 `MatterIdentity` in `MatterShell`, in both branches. 45 min
  - The breadcrumb, the avatar, a serif h1 of the client's name, and a case line (description, matter number, incident date with a chip), plus the stage track.
  - `document.title`.
  - `ProviderView` gets a heading-level prop.
- [x] U12 `StageTrack`. 30 min
  - Steps move to `lib/labels.ts`, named as `STAGE_LABELS`.
  - Visible "Step N of 5"; settled and closed never read "Step 6 of 5".
  - The inferred marker and the chip.
  - `RoadmapCard` is deleted.
- [x] U13 `MarginCited` rows. 60 min
  - Also `BottomLine` (26px serif), `WhereItStands` (one sentence per row) and `OpenQuestions` (neutral).
  - Chips go in a 14rem gutter, and drop under the text below about 40rem.
  - D12 marks keep their inline chip.
- [x] U14 `WhatHappened`, after B11. 30 min
  - The incident account, up to 3 injuries, and the liability fact, each a `MarginCited` row.
- [x] U15 `NowStrip` and the money row. 60 min
  - The cells: next step (overdue, else a task, else a deadline that isn't the statute), statute (amber within 90 days, red once passed), last client contact (words as well as amber), and the counts.
  - `KpiStrip` moves to the Overview as a compact row.
  - `CaseMetadata`, `MetadataItem` and `MatterHeader` are deleted.
- [x] U16 `KeyEvents`, after B12. 60 min
  - A numbered `<ol>`, oldest first; each lane shown as a dot plus a word.
  - "Full timeline" goes to `?view=attorney&feed=timeline`, so the feed toggle lives in the URL.
- [x] U17 Overview assembly. 40 min
  - `ChangesSince` shows at most 5 rows, moves to the bottom, and its copy changes to fit.
  - The For Attorney action board loses its count tiles.
- [x] A11Y 60 min
  - Reflow: the rail collapses below `lg`, and grids use `auto-fit`.
  - Drawer focus returns to the opener.
  - `role="status"` for status changes.
  - The action board becomes a `<table>`.
  - Focus after "+N more", and `aria-expanded`.
  - A skip link.
  - Page text in a `<details>` (after B13).

**Lead, reviewer, critic**
- [x] L1 lead: update `docs/ui.md`, `docs/architecture.md` and `docs/project.md`.
- [x] L2 lead: retake all six screenshots on the synthetic matter (D33).
- [x] V6 reviewer: README alt text and views, `docs/submission.md:49`, and `check.sh` free of FAIL.
- [x] C4 critic: the 90-second test on the real matter from the first screen alone; every chip in the new blocks opens a source holding its text. Every chip held; four readings misled (Pass 4, 3ad4026), fixed under D40.

**D40, the critic's Pass 4 fixes (code only, no model call)**
- [x] Backend: a deadline read from a Clio task carries the task's status, so a met statute is neither "passed" nor upcoming; key events drop deadlines; `restated_by` counts records, not pages.
- [x] ui-builder: "Met" for a met statute; earlier stages not marked completed; two liability facts; injuries by body region (the treating providers' finding first, no count); "Overdue" and "open requests" labels; the coverage label not repeated.
- [x] Litigation history: the Manager approved the re-read (2026-10-08), see D41 below.

**D41, litigation history and the provider updates (Manager, 2026-10-08)**
- [ ] B14 backend: kind `litigation_event` (internal by default-deny, in the key events, schema upgraded in place); provider updates show stage moves only, labelled by code.
- [ ] P14 pipeline: the extraction prompt records court events as `litigation_event` with the filing, service or decision date; `status_change` only for stage moves. Estimate, then the runbook: a trial on a copy, a backup, the run (stop at $1).
- [ ] L3 lead: the label and lane for the new kind; check the story on the real matter after the run; the critic re-checks the new rows.

## Calls (D8: option A now, B later)

The Manager's request: when the next step on the case is a follow-up or a check-in, call the person from the app, and have AI transcribe the call and take the notes so the attorney can focus on the conversation.

**What it does**
- **A Calls view** lists who to call next: open action-board items waiting on someone, each with the contact's phone number from Clio (read-only), the item's source chip, and the days since the last contact.
- **Consent before transcription.** California requires every party's consent to record a confidential call (Cal. Penal Code section 632). The app asks the attorney to confirm that the other party agreed, and logs that with the call. This is a design rule here, not legal advice.
- **AI notes after the call.** When the call ends, one model call through `digest/llm.py` turns the transcript into notes: a summary, commitments, dates and amounts mentioned, and follow-ups.
  - The call is started by the user, never on page load (rule 5).
  - Every note cites a span of the transcript, checked in code like document quotes (rule 3).
- **Storage.**
  - Notes become facts under a new source type, `call`, stored in Clarity's database. Nothing is written to Clio (rule 1).
  - Call notes are internal under default-deny (rule 4).
  - The call updates "last contact".

**Two ways to place and hear the call (D8)**
- **(A) Hand-off plus your side.** A `tel:` link opens the computer's phone app or your phone, and the browser's speech recognition transcribes your microphone.
  - Costs: no account, no new dependency.
  - Limits: it hears only you unless the call is on speaker, and Chrome sends the audio to Google's speech service.
- **(B) In-app calling.** A telephony provider (for example Twilio Voice) places the call from the browser and transcribes both sides, and can play a consent announcement.
  - Costs: an account you create, a phone number, per-minute charges, new dependencies.
  - Infrastructure: a public URL for the provider's webhooks, which means a tunnel, since Clarity runs on localhost.

Both write the same transcript source, so (B) can later replace (A)'s audio without changing the notes pipeline.

**Rules for any test:** never call anyone from the real matter; use your own phone or a teammate's. The notes step needs model API credit.

## Demo moments

| # | What a judge sees | Owner | Ready by |
|---|---|---|---|
| 1 | Open the matter: the brief, with a chip on every sentence, opens the scanned page with the quote highlighted | ui-builder | T+2:00 |
| 2 | The KPI tiles and every provider's bill total are right on the real matter, and each opens its source | backend, critic | T+2:00 |
| 3 | The new feature, on the real matter (D2) | backend, ui-builder | T+3:00 |
| 4 | A provider link shows only what the attorney allowed; the firm's preview is identical | backend, critic | T+2:30 |

## Backlog

Owner, item, budget. Track A review references are in `docs/progress.md` under "Track A review against the architecture".

**Pipeline** (prefer `/ecc:orch-fix-defect`: failing test first)
- [x] P1 `balance_cents` and `high_cents` may be stored 100 times too small: the prompt names them in cents but says only `amount` is in dollars (`digest/prompts/extract_page.txt`, `digest/payloads.py`). 30 min
- [x] P2 A partly failed sync counts as clean, so records missed once are never pulled again; a failed download of an updated document keeps the old file because its new ETag is saved first (`clio/sync.py`). 40 min
- [x] P3 A sync stopped by anything but `ClioError` stays unfinished (`clio/sync.py`). Pairs with B3. 20 min
- [x] P4 A failed mapping call wipes KPI, stage and ledger facts; pages extracted without providers never get attribution later (`digest/mapping.py`, `digest/extract.py`). 40 min
- [x] P5 The policy-limit cross-check is missing: `digest/merge.py` checks specials only. 30 min
- [x] P6 A second digest can still call the model (after an errored call, dropped score ids, or a dedup-removed custom-field fact) (`digest/extract.py`). 30 min
- [x] P8 D7: rename the matter-derived insurer term in `digest/prompts/map_roles.txt` and the policy-limits term in `digest/prompts/significance.txt` (the allowlist hides the second, so check both by eye), and bump each prompt's version string. A changed prompt misses the cache, so the next digest re-runs those calls and needs the Manager's go-ahead and API credit. 15 min
- [x] P9 D14: the brief prompt asks for the facts the headline rests on, and the merge step stores them with the headline. Bump the prompt version. 20 min
- [x] P10 (run 2026-10-08 on Anthropic, D36: Gemini's free tier answered 4 of 14 attempts after the reset; a trial on a database copy passed, then (a) at 03:49 and (b) at 03:50 on the real database, 16 paid calls, $0.17, a backup before each) D13: re-digest once. First estimate the model calls that will miss the cache and the cost, and stop. The lead brings the estimate to the Manager, then run it. Needs the model settings in the root `.env`. 20 min plus the run
- [x] P7 Minor: split `mapping.py`; move retry counts, timeouts and batch sizes into `config.py`; remove the dead code in `payloads.py` and `records.py`; keep case text out of the warning log in `llm.py`; send JPEGs as `image/jpeg`. 40 min

**Backend**
- [x] B1 Server side of the new feature (D2), with tests on the real matter. 90 min
- [x] B2 Check the four KPI tiles and every provider's bills total against the real matter, with the critic. 20 min
- [x] B4 D12 and D14: when the brief is served (`services/brief_view.py`), run each sentence's amounts and dates through the draft checker's matcher against today's facts and computed totals. A sentence that disagrees gets a "differs" mark with today's figure and its fact ref. Check the headline's citations like a sentence's. Additive contract change. 40 min, after B1
- [x] B3 Report sync failures that happen before the run row exists (no token, no matching matter) instead of only logging them (`api/ops.py`). Pairs with P3. 20 min

**UI**
- [x] U1 D3: restore the brief's sentences with a chip on each. Keep the chip rendering in one place so a later switch to "the section is clickable and opens its documents" is a small change. 40 min
- [x] U2 Check the source drawer, brief, KPI strip and injuries list on the real matter and fix what breaks (`docs/tracks/b-firm.md`, B3 and B4). 40 min
- [x] U3 Check the provider page on the real matter and fix what breaks (`docs/tracks/c-provider.md`). 30 min
- [x] U4 UI of the new feature (D2). 90 min
- [x] U5 Loading, empty and error states on the screens of the demo moments (done in U8). 20 min
- [x] U7 D12 and D14: show a brief sentence's "differs from the file" mark with today's figure and its chip, and show the headline's chips once the brief carries them. Also show B3's `start_failure` in the footer. 30 min, after B4

**From the critic's first pass** (`docs/reviews/critic.md`, Pass 1; the numbers are its finding numbers)
- [x] P11 pipeline, brief input: 40 min, applied at the re-digest
  - computed totals reach the brief model with the fact ids behind them (#1);
  - each row carries its source title and date, so two exams are not merged (#3);
  - no open question that the page already answers (#6);
  - one date format (#16).
- [x] P12 pipeline: a neutral title for ledger facts (#10); no trailing space in the stage label (#16). 15 min
- [x] B5 backend, repairing `049da3d`: 30 min
  - the specials tile must not say "disagree" and "matches" at once (#2);
  - a one-ended valuation must not become a point value;
  - per-occurrence limits come back.
- [x] B6 backend: the header's incident-date chip opens a source that contains the date (#7). 20 min
- [x] B7 backend with pipeline: a record request closes when a later records-received fact answers it, and restatements collapse to one (#8). 45 min
- [x] B8 backend:
  - one row per fact in the ranked feed, citing every record that states it, like the injuries list (#9);
  - "last movement" comes from the latest dated case event (#12);
  - a document's own date in the drawer (#13);
  - no duplicate limits on the provider page (#16). 40 min
- [x] B9 backend: "no bills on file" instead of $0 (#15; D16). 20 min
- [x] P13 pipeline (D19, D20): the extraction prompt records which policy a limit belongs to, and gives economic damages and recovery caps kinds of their own. Add a command that re-extracts named pages only. Run it after the Manager approves the estimate (P10 b). Bump the prompt version. 45 min plus the run
- [x] B10 backend (D19, D20): the contract changes to match P13 (new kinds, the policy field, both additive) with `types.ts`; the new kinds go into visibility as internal; the Coverage tile leads with the defendant limit and labels the others. 40 min
- [x] U9 ui-builder (D19): the Coverage tile shows the leading limit and the labelled client policies under it. 20 min, after B10
- [x] U8 ui-builder:
  - loading, empty and error states (U5);
  - chips in the share preview open their sources;
  - "Uploaded" when a document has no date of its own (#13);
  - "No bills on file" once B9 lands. 40 min

**Researcher**
- [x] R0 A brief for the chosen feature: how comparable tools present it, and the rules for the builders. 30 min
- [x] R1 A brief for Calls (A). 30 min Covering:
  - the browser speech recognition API: support, limits, and where the audio goes;
  - how `tel:` links behave on Windows and macOS;
  - consent wording for a call that is transcribed;
  - how comparable legal tools present call notes.

**Calls (after the draft checker, D9)**
- [x] C-B backend: the call model and routes, built only on new tables, so nothing needs `cli reset` (that would wipe the synced matter). 90 min
  - **Who to call next:** open action items waiting on someone, joined with each contact's phone number from the synced Clio contacts.
  - **Start a call**, with the consent confirmation logged.
  - **Save the transcript.**
  - **Request notes.** The request starts a background run the way `api/ops.py` starts a digest, because no request handler calls a model.
  - **Sourcing:** a transcript is a source, so a note's chip opens the transcript with its quote highlighted in the drawer.
  - **Visibility:** call notes are internal under default-deny.
- [x] C-P pipeline: a versioned prompt in `digest/prompts/` turns a transcript into notes (a summary, commitments, dates and amounts mentioned, follow-ups), through `digest/llm.py`. 60 min
  - Every note carries a quote that code checks against the transcript (reuse `verify.py`); a note whose quote fails is dropped.
  - Dates and amounts are parsed in code.
- [x] C-U ui-builder: a Calls view in the sidebar (`?view=calls`). 90 min
  - **The list:** who to call next, with the source chip of the item behind each call, the phone number and the days since the last contact.
  - **Placing the call:** a consent step, then the `tel:` hand-off.
  - **During the call:** a live transcript from the browser's speech recognition, which says plainly that only this microphone is heard.
  - **After the call:** an end-call action that requests notes, and the notes with chips into the transcript.
- [ ] C-T The test call is the Manager's: call your own phone or a teammate's, never anyone in the matter. The lead watches it in the browser.

**Reviewer**
- [x] V1 Triage the first `check.sh` run to the owners. The lead's setup run on 2026-10-06 (before any trial commit):
  - **Lint:** 13 import-order errors (ruff I001), all in `backend/tests/`, all fixable with `ruff check --fix`. 10 belong to backend; pipeline owns `test_clio_client.py`, `test_llm.py` and `test_merge.py`.
  - **No case data:** 22 hits, which need decision 3.
  - **Passing:** Clio read-only (8 passed), hygiene (4 passed), backend tests (98 passed), frontend types.

  30 min
- [x] V2 README: verified / built, lightly tested / half-done, cost per case, a repository map. 40 min (1d04d4e, 862632e, 5068bf1)
- [x] V3 One screenshot per view in `docs/screenshots/`, on the synthetic matter (D33), taken by the lead from the reviewer clean clone. 20 min (d62208c, 8a5d23d; the provider two are retaken once D35's lien label lands)
- [x] V4 Fill the brackets in `docs/form-answers.md` from measured numbers. 15 min (e09aebf; team size, the clip link and the Gemini runs are left to the lead)
- [x] V5 Clean-clone run, timed, following the README exactly. 30 min (e22a5ae, ea2ef35: two check.sh fixes it found)

**Critic** (each hour)
- [x] C1 First pass: trace three numbers on screen to their sources on the real matter; walk demo moments 1 to 4.
- [x] C2 Second pass after the new feature lands, including `/ecc:orch-review` on the branch's diff.
- [ ] C3 Third pass after the model runs (D34): the re-digested brief and the re-read coverage limits on the real matter.

## Milestones

T+0:00 is 2026-10-07 00:30 PDT. The planned clock times were targets; the Done column gives the time each milestone was reached, from the commits.

| T+ | Clock | Milestone | Done |
|---|---|---|---|
| 0:00 | 00:30 | D2, D3, D7 to D11 decided; setup committed; servers up; workers started | [x] 00:30 |
| 0:30 | 01:00 | P8 done; first defect has a failing test; lint fixed by its owners | [x] 00:39 (P8 at 00:31; lint was a config fix, 4b40d16) |
| 1:00 | 01:30 | First critic pass (C1); P1 and P3 fixed | [x] 00:54 |
| 2:00 | 02:30 | Demo moments 1 and 2 on real data; draft checker server side (B1) done | [x] 01:15 |
| 3:00 | 03:30 | Draft checker UI (U4) on real data; second critic pass (C2); Calls starts | [x] 01:55 |
| 5:30 | 06:00 | Calls on real data, and the Manager's test call (C-T) | [ ] Calls built and checked 01:53; C-T not done |
| 6:00 | 06:30 | **Feature freeze.** Fixes, checks and the README only | [x] last feature commit 02:53; recorded 09:29 (D32) |
| 6:30 | 07:00 | `check.sh` shows no FAIL; README and screenshots done; trial retro written | [x] check.sh clean; README and 6 screenshots 10:52 (Oct 7); model runs 03:50 (Oct 8, D36); retro written |

## Cut order

When a milestone slips, cut from the top. Never cut a fact's source.

1. P7 (minor items)
2. U5 (states)
3. The "don't send" lock in feature (a), keeping the amount and date checks
4. V5 (clean-clone run), done by hand later
5. P6

## Out of scope

Deployment, real authentication, writing anything to Clio, a re-sync or re-digest without the Manager's go-ahead (it needs a working Clio token and API credit).

## Trial measures (for the kit's retro)

The lead fills these in at the end; each role notes its own in its STATUS row as it goes. Measured at 10:10, from the commits and the agents' transcripts; the model runs (D34) and three screenshots are still open.

- **Clock:** kickoff at 00:30. Features ran from 00:30 to 02:53, then nothing until 09:29, when the freeze was recorded. Freeze work ran from 09:29.
- **Commits per role:** 114 commits after the setup commit, counted by the owned paths each one touches. pipeline 27, ui-builder 27, backend 26, lead 23, reviewer 7, critic 2, researcher 2 (the lead committed these for it).
- **Ownership hook:** it blocked no edits in any of the 12 agent transcripts. The logs can't tell whether agents stayed in their lanes or the hook never fired for a subagent. It was tested only by piping sample input at setup.
- **GateGuard prompts:** the lead had 43 before the trial (the Corro analysis, the kit and the setup) and 8 during it. Backend had 2, reviewer 5, pipeline 1 and ui-builder 1. Nearly all the friction fell on the lead.
- **Waits on "Blocked on":**
  - The researcher waited for the lead to commit its briefs, since it has no shell.
  - Backend waited for API restarts (D29 fields).
  - ui-builder sat idle on Calls until the contract was written down (D22), then built against it.
  - Pipeline's trial process slept for 26 minutes on a wait the API asked for, which nothing capped (D34).
- **Collisions:** none in the shared checkout. In one cross-role break, a contract change broke ui-builder's typecheck, and D23 now requires the contract owner to run it.
- **First `check.sh` with no FAIL:** at 1cd54d0 (00:47), reported by the critic at 00:54, so T+0:24.
- What to change in the kit. Found so far:
  - **During setup:** role files hard-coded the template's paths (fixed in the kit); the case-data test flagged one-word labels such as "Work" (fixed); GateGuard asked about 25 times during setup.
  - **During D7:** the allowlist is global, so allowing a term for docs also hides it in prompts. Entries need a path scope.
  - **First hour:**
    - The researcher role has no shell, so it cannot commit its briefs and the lead commits them.
    - Uvicorn reloads on every backend edit, so the browser saw transient 502s while agents worked.
    - Ruff ran from the repository root reported import-order errors that a missing `src` setting caused; the fix was config, not code.
    - Restoring the brief exposed a stored sentence written before the bill fix. Catching a stale model output early is a job for the critic.
  - **Second hour:**
    - Vite needed a restart after parallel edits left a stale module, and the API needed restarts because uvicorn reload missed changes on Windows. The lead runs the servers, so this falls to the lead; a watcher would help.
    - A contract change by one role broke another role build: the contract owner must run the other side typecheck.
    - The lead wrote decision times from estimates rather than the clock; corrected. Take times from `date` or the commits.
  - **After the freeze:**
    - **Decision times drifted again.** D22 to D34 were off by up to six and a half hours (D32 said 03:20; it was recorded at 09:29). A rule in a file didn't fix this. The kit needs a `/decide` skill that appends the row with the time from `date`.
    - **Test the model API with one call in the first hour.** Gemini's free tier answered none of 12 attempts with overload 503s and quota 429s, and that was found after the freeze. A rolling-window limiter let a sixth attempt through exactly 60 s after the first, which Google counted against the minute. Space attempts evenly, cap any wait the API asks for, and log the quota id from the first error.
    - **Run the clean clone early.** V5 found two `check.sh` problems that only a fresh checkout shows: a false FAIL on the synthetic matter, and a leftover export that blocked `cli reset`.
    - **Screenshots double as a UI review.** Taking them on the synthetic matter found two layout bugs the real-matter views hid: a money range cut off on a tile, and a lien that reads like a second bill. Take them before the freeze.
    - **Background agents need a time limit.** A subagent that waits on its own background process waits as long as that process does. When a report is late, the lead checks the process and its log.
    - **The ownership hook needs a live self-test at `/kickoff`.** It should try one edit outside the role's paths and expect the block. Zero blocks in a day says nothing on its own.
  - **The model runs (2026-10-08):**
    - **Free tiers cannot carry a real run.** After the quota reset, Gemini's free tier answered 4 of 14 attempts. Its terms also let Google use the content, which is wrong for a real person's file. The paid Anthropic tier answered 22 of 22 calls on the first try, for $0.19 including the trial. Budget a paid key from the start; it costs cents.
    - **Trial on a copy, then back up, then run.** The trial caught that Gemini dropped people facts, and passed Haiku before anything touched the real database. Keep this gate in the kit's runbook.
    - **The critic after a model run finds what tests can't.** Pass 3 found that the re-read model left one limit untagged and another without a basis, and the tile then warned of a disagreement no record makes.
    - **The contract rule broke again.** Backend committed a contract change knowing the frontend typecheck failed (a98001f), against D23. The kit needs a pre-commit check that runs the other side's typecheck when `schemas.py` or `types.ts` changes.
    - **The lead printed a secret.** A masking `sed` covered `KEY=` lines but not commented-out ones, and an old key was shown in the session. Mask by matching the value, never by line shape; better, never print `.env`.
