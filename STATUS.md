# Status

Each role edits only its own row. Keep cells under 15 words. Update with /status. The hackathon's own status is history in docs/progress.md.

| Role | Now | Next | Blocked on | Needs decision | Updated |
|---|---|---|---|---|---|
| lead | Verified Calls in the browser (targets, chips, typed line, no-model notes, consent gate), No bills on file, coverage tile | Critic Pass 2 findings; then freeze and the reviewer | Manager: .env model settings; the test call (C-T) | Approve (a), (b), a re-sync; retry-failed button | 02:05 |
| pipeline | Live test stopped at errors (scratch DB, $0): flash 503 overloaded after 5 tries; gemini-2.5-pro 404, not offered to new users | Trial on a copy, after a model fix and a retest | Manager: a merge model (Google suggests gemini-3.1-pro-preview) and its prices | Merge model choice; retry flash later | 02:41 |
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
