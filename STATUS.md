# Status

Each role edits only its own row. Keep cells under 15 words. Update with /status. The hackathon's own status is history in docs/progress.md.

| Role | Now | Next | Blocked on | Needs decision | Updated |
|---|---|---|---|---|---|
| lead | D36 runs $0.17; D37 fixes in; screenshots retaken (ca080ab); check.sh clean (387) | Pushed; standing by | | Manager: clip link; test call (C-T) | 04:56 |
| pipeline | Freeze fixes done: 76d49cb reextract estimate skips failed calls; f37a110 rewritten brief updates created_at. 371 tests pass | Standing by | | | 2026-10-08 03:59 |
| backend | D40: deadline status fe07ba2 (contract: DeadlinePayload.status); no deadlines 9c5b491; per-record 462c8aa; 428 | Stand by | reviewer: rerun cli seed-dev in the clone (:5183, API :8010) | | 2026-10-08 14:59 |
| ui-builder | Region rows by records stating them 53523da; D40 3277eba, c9be7b4; check.sh clean | Lead checks the injury rows | | Region rows: diagnosis before served order on ties? | 2026-10-08 15:01 |
| researcher | Done: briefs/model-pricing.md, paid-tier prices; unblocks lead and pipeline (P10, D34) | Idle | lead: commit model-pricing.md (no shell) | Manager: which paid provider and model for the runs | 2026-10-08 |
| critic | C4 done (3ad4026): met statute shows red "passed"; "All 192 injuries"; incident cited 179x, disputed | Stand by | | Met-statute status; drop past deadlines from story; litigation re-read; request direction; liability rows | 2026-10-08 14:43 |
| reviewer | D40 in README (0bba19d); check.sh no FAIL, 428. Clone at 0bba19d, servers restarted for D40: http://localhost:5183/matters/1 (API :8010), up | Keep clone up for L2 retakes; drop screenshot note after L2 | | | 2026-10-08 15:08 |

## Stubs and shortcuts

New ones only, one line each when written: what, why, file. The hackathon's are in docs/progress.md and docs/tracks/*.md; the README lists both.

- B3: a sync or digest that fails before its run row is held in server memory, so a restart forgets it (backend/app/services/jobs.py)
- B1: the draft checker reads amounts only with $, USD or "dollars", and dates only with a month name or numeric form (backend/app/services/text_mentions.py)
- P6: a failed model call is not retried until `cli digest --retry-failed`; the run's error says how many were skipped (backend/app/digest/llm.py)
- P13: `cli reextract --dry-run` prices a selection from average recorded costs, an upper bound; cached answers cost less (backend/app/digest/reextract.py)
- C-P: a date said on a call without a year is placed at the nearest such day to the call, within six months, else left out (backend/app/digest/call_notes.py)
- P4 known issue: pages read before a provider was known never get that provider. Fix (1): store provider_name_as_written on facts (new column, needs reset or a migration), re-resolve in code after mapping, no model call. Fix (2): re-read pages when the provider list changes, one call per page (backend/app/digest/extract.py)
