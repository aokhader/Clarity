# Status

Each role edits only its own row. Keep cells under 15 words. Update with /status. The hackathon's own status is history in docs/progress.md.

| Role | Now | Next | Blocked on | Needs decision | Updated |
|---|---|---|---|---|---|
| lead | D38-D40 Overview pass done: 90-second first screen (9 of 12 on the real matter at 1440x900), legal-memo restyle, margin citations; Lighthouse a11y 100 on all firm views and /p/:token; critic Pass 4 fixed (D40); six screenshots retaken (506267f) | Waiting for the reviewer's README pass, then check.sh | | Manager: litigation-history re-read (cents, D40); push; clip link; test call (C-T) | 15:18 |
| pipeline | P14 run done: 13 pages, 7 litigation events, 0 failures, $0.086 with trial | Standing by | | Story shows no litigation event: dated ones score below 88 | 2026-10-08 18:43 |
| backend | B15 b732ad9: court events pinned in key events (3 on the real matter); 462 tests | Stand by | | | 2026-10-08 18:48 |
| ui-builder | Region rows by records stating them 53523da; D40 3277eba, c9be7b4; check.sh clean | Lead checks the injury rows | | Region rows: diagnosis before served order on ties? | 2026-10-08 15:01 |
| researcher | Done: briefs/model-pricing.md, paid-tier prices; unblocks lead and pipeline (P10, D34) | Idle | lead: commit model-pricing.md (no shell) | Manager: which paid provider and model for the runs | 2026-10-08 |
| critic | C4 done (3ad4026): met statute shows red "passed"; "All 192 injuries"; incident cited 179x, disputed | Stand by | | Met-statute status; drop past deadlines from story; litigation re-read; request direction; liability rows | 2026-10-08 14:43 |
| reviewer | D41 in README and form (c6eca72); check.sh no FAIL, 462. Clone reseeded, up: http://localhost:5183/matters/1 (API :8010) | Standing by | | lead: retake provider page and preview (pre-D41 label); a cli command for upgrade_schema? | 2026-10-08 18:56 |

## Stubs and shortcuts

New ones only, one line each when written: what, why, file. The hackathon's are in docs/progress.md and docs/tracks/*.md; the README lists both.

- B3: a sync or digest that fails before its run row is held in server memory, so a restart forgets it (backend/app/services/jobs.py)
- B1: the draft checker reads amounts only with $, USD or "dollars", and dates only with a month name or numeric form (backend/app/services/text_mentions.py)
- P6: a failed model call is not retried until `cli digest --retry-failed`; the run's error says how many were skipped (backend/app/digest/llm.py)
- P13: `cli reextract --dry-run` prices a selection from average recorded costs, an upper bound; cached answers cost less (backend/app/digest/reextract.py)
- C-P: a date said on a call without a year is placed at the nearest such day to the call, within six months, else left out (backend/app/digest/call_notes.py)
- P14: extract_record stays v3, so notes and emails still read court events as other; any bump re-reads the matter's custom fields, since their marker is the cache key (backend/app/digest/extract.py)
- P14: `reextract --keep-brief` leaves the brief as it was; the next full digest writes it, one merge call (backend/app/cli.py)
- P14 run: the brief is kept and now stale against the facts, so the next digest (CLI or in-app) makes one Sonnet call (backend/app/digest/brief.py)
- P4 known issue: pages read before a provider was known never get that provider. Fix (1): store provider_name_as_written on facts (new column, needs reset or a migration), re-resolve in code after mapping, no model call. Fix (2): re-read pages when the provider list changes, one call per page (backend/app/digest/extract.py)
