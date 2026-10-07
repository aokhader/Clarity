# Status

Each role edits only its own row. Keep cells under 15 words. Update with /status. The hackathon's own status is history in docs/progress.md.

| Role | Now | Next | Blocked on | Needs decision | Updated |
|---|---|---|---|---|---|
| lead | 6 of 6 screenshots (8a5d23d); D34 runs wait for the free-tier retry; D35 lien kind with backend | Retake provider shots after D35; model runs later (D34) | backend: D35 kind, then ui-builder | Manager: push kit-trial; test call (C-T) | 10:25 |
| pipeline | cli auth fix e4c7db8 (names the missing CLIO_CLIENT_ID/SECRET, exits 1, no URL). Pacing and wait cap 71a9be6. Trial stopped; copy kept | Retry of (a), (b) and the trial waits on D34; the lead starts it | | | 10:15 |
| backend | D35 contract: ProviderItemOut.kind 'bill' or 'lien' on bills items, else null; types.ts mirrored | Freeze fixes only; ui-builder can label lien rows (01d6e41, :8000 serves it) | | | 10:35 |
| ui-builder | D35: lien rows labelled cfc121b; update lists liens apart 612945b; checked 1440, 1280 | Stand by | | | 10:42 |
| researcher | Done: briefs/draft-checker.md (backend B1, ui-builder U4); briefs/calls.md (C-B, C-P, C-U) | Idle | lead: commit both briefs; researcher has no shell | Calls: let Manager type a test number, stored locally? | 01:05 |
| critic | C2 done: Case value leads with recovery cap; lock bypassed; incident date falsely locked | Pass 3 after the re-digest (D13) | | Incident date shareable? Near-figure flag; coincident dates warn, not lock | 01:58 |
| reviewer | Done: V5, V2, V4. README final (f3f856d). Clone servers stopped; clone folder kept. check.sh at c097f44: no FAIL, 369 tests | Stopped. GateGuard prompts: 4 | lead: README cost and form placeholders after D34 runs; team size; clip link | | 10:52 |

## Stubs and shortcuts

New ones only, one line each when written: what, why, file. The hackathon's are in docs/progress.md and docs/tracks/*.md; the README lists both.

- B3: a sync or digest that fails before its run row is held in server memory, so a restart forgets it (backend/app/services/jobs.py)
- B1: the draft checker reads amounts only with $, USD or "dollars", and dates only with a month name or numeric form (backend/app/services/text_mentions.py)
- P9: headline_fact_ids is written beside BriefContent's fields until backend adds it to the contract (backend/app/digest/merge.py)
- P6: a failed model call is not retried until `cli digest --retry-failed`; the run's error says how many were skipped (backend/app/digest/llm.py)
- P13: `cli reextract --dry-run` prices a selection from average recorded costs, an upper bound; cached answers cost less (backend/app/digest/reextract.py)
- C-P: a date said on a call without a year is placed at the nearest such day to the call, within six months, else left out (backend/app/digest/call_notes.py)
- P4 known issue: pages read before a provider was known never get that provider. Fix (1): store provider_name_as_written on facts (new column, needs reset or a migration), re-resolve in code after mapping, no model call. Fix (2): re-read pages when the provider list changes, one call per page (backend/app/digest/extract.py)
