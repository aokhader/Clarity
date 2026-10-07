# Status

Each role edits only its own row. Keep cells under 15 words. Update with /status. The hackathon's own status is history in docs/progress.md.

| Role | Now | Next | Blocked on | Needs decision | Updated |
|---|---|---|---|---|---|
| lead | Feature freeze (D32). Gemini native provider live; trial on a database copy running | Review the trial; then back up and run (a), (b); screenshots; critic Pass 3 | | Manager: the test call (C-T) after notes can run | 03:20 |
| pipeline | Diagnostics passed: 3.8-flash no schema 200 (101 s, thinking 126); flash-lite full request 200, responseJsonSchema accepted, JSON valid. The 503s were capacity, not our request. Spent ~$0.001 | Stopped; waiting for the lead | | Next step for the trial | 03:04 |
| backend | K7 dde2e3c; D29 6b044aa: digest retry_failed body, RunStatusOut.cached_failed_calls. Standing by | Freeze fixes only | lead: restart :8000 for D29 fields | | 02:30 |
| ui-builder | D29 retry control 15dc3c3 (not clicked: model switch under way) | Stand by | | | 02:31 |
| researcher | Done: briefs/draft-checker.md (backend B1, ui-builder U4); briefs/calls.md (C-B, C-P, C-U) | Idle | lead: commit both briefs; researcher has no shell | Calls: let Manager type a test number, stored locally? | 01:05 |
| critic | C2 done: Case value leads with recovery cap; lock bypassed; incident date falsely locked | Pass 3 after the re-digest (D13) | | Incident date shareable? Near-figure flag; coincident dates warn, not lock | 01:58 |
| reviewer | | | | | |

## Stubs and shortcuts

New ones only, one line each when written: what, why, file. The hackathon's are in docs/progress.md and docs/tracks/*.md; the README lists both.

- B3: a sync or digest that fails before its run row is held in server memory, so a restart forgets it (backend/app/services/jobs.py)
- B1: the draft checker reads amounts only with $, USD or "dollars", and dates only with a month name or numeric form (backend/app/services/text_mentions.py)
- P9: headline_fact_ids is written beside BriefContent's fields until backend adds it to the contract (backend/app/digest/merge.py)
- P6: a failed model call is not retried until `cli digest --retry-failed`; the run's error says how many were skipped (backend/app/digest/llm.py)
- P13: `cli reextract --dry-run` prices a selection from average recorded costs, an upper bound; cached answers cost less (backend/app/digest/reextract.py)
- C-P: a date said on a call without a year is placed at the nearest such day to the call, within six months, else left out (backend/app/digest/call_notes.py)
- P4 known issue: pages read before a provider was known never get that provider. Fix (1): store provider_name_as_written on facts (new column, needs reset or a migration), re-resolve in code after mapping, no model call. Fix (2): re-read pages when the provider list changes, one call per page (backend/app/digest/extract.py)
