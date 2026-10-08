# Status

Each role edits only its own row. Keep cells under 15 words. Update with /status. The hackathon's own status is history in docs/progress.md.

| Role | Now | Next | Blocked on | Needs decision | Updated |
|---|---|---|---|---|---|
| lead | D36 runs $0.17; D37 fixes in; screenshots retaken (ca080ab); check.sh clean (387) | Pushed; standing by | | Manager: clip link; test call (C-T) | 04:56 |
| pipeline | Freeze fixes done: 76d49cb reextract estimate skips failed calls; f37a110 rewritten brief updates created_at. 371 tests pass | Standing by | | | 2026-10-08 03:59 |
| backend | B11 c9135dd, B12 4817dfd, B12a af58146 (incident row is the account), B13 39c2286; 410 tests | Stand by for the lead's real-matter check | | | 2026-10-08 13:06 |
| ui-builder | Money e2142ac, U14 5974267, U16 2374edd, A11Y a9abd4f; check.sh clean | Lead's 90-second test, Lighthouse, keyboard walk | | | 2026-10-08 13:51 |
| researcher | Done: briefs/model-pricing.md, paid-tier prices; unblocks lead and pipeline (P10, D34) | Idle | lead: commit model-pricing.md (no shell) | Manager: which paid provider and model for the runs | 2026-10-08 |
| critic | C3 done (72d74de): Coverage false disagree (1985, 2012); driver policy labelled client's; brief chips skip pages | Stand by | | Coverage rule (1); party-policy enum; provider limits defendant-only; in-file-not-on-link wording | 2026-10-08 04:11 |
| reviewer | D37 in README and form (92cb8f1); check.sh 10ffbb3 no FAIL, 387. Clone seed-dev at 10ffbb3: http://localhost:5183/matters/1 (API :8010), up | Keep clone servers up for the lead's retakes | | | 2026-10-08 04:54 |

## Stubs and shortcuts

New ones only, one line each when written: what, why, file. The hackathon's are in docs/progress.md and docs/tracks/*.md; the README lists both.

- B3: a sync or digest that fails before its run row is held in server memory, so a restart forgets it (backend/app/services/jobs.py)
- B1: the draft checker reads amounts only with $, USD or "dollars", and dates only with a month name or numeric form (backend/app/services/text_mentions.py)
- P6: a failed model call is not retried until `cli digest --retry-failed`; the run's error says how many were skipped (backend/app/digest/llm.py)
- P13: `cli reextract --dry-run` prices a selection from average recorded costs, an upper bound; cached answers cost less (backend/app/digest/reextract.py)
- C-P: a date said on a call without a year is placed at the nearest such day to the call, within six months, else left out (backend/app/digest/call_notes.py)
- P4 known issue: pages read before a provider was known never get that provider. Fix (1): store provider_name_as_written on facts (new column, needs reset or a migration), re-resolve in code after mapping, no model call. Fix (2): re-read pages when the provider list changes, one call per page (backend/app/digest/extract.py)
