# Status

Each role edits only its own row. Keep cells under 15 words. Update with /status. The hackathon's own status is history in docs/progress.md.

| Role | Now | Next | Blocked on | Needs decision | Updated |
|---|---|---|---|---|---|
| lead | Verified U1, B1 (on the real matter), U8 drawer and preview; restarted Vite and the API | Critic pass 2 after U4 and B4; reviewer near the freeze | Manager: model settings in the root .env | Approve the re-digest and re-extraction estimate when pipeline reports it | 02:50 |
| pipeline | P13 reextract command d219555. Backend, agree? kinds economic_damages, recovery_cap (amount_cents); PolicyLimitPayload.policy: defendant_liability, client_no_fault, client_um_uim, client_other, nullable | P13 prompt and payloads once backend agrees | backend: P13 names; Manager: .env lacks EXTRACT_MODEL, MERGE_MODEL, four prices | P10: (a) re-digest 4-6 calls ~$0.20; (b) 9 records, 0 pages, ~$0.19 incl. brief | 01:14 |
| backend | B6 441743c: incident chip cites the Clio field. Now B7 (requests) | B8, B9, B10 | lead: restart :8000; it has not reloaded since B5 (incident still old) | | 01:11 |
| ui-builder | U4 951fd3f 6233d3a; U7 6fb76e3 944f79b; KPI labels 84d3342 | U8 no-bills after B9; U9 after B10; drawer document date after B8 | backend: B8 document-date field; B9 nullable billed_cents; B10 | | 01:13 |
| researcher | Done: briefs/draft-checker.md (backend B1, ui-builder U4); briefs/calls.md (C-B, C-P, C-U) | Idle | lead: commit both briefs; researcher has no shell | Calls: let Manager type a test number, stored locally? | 01:05 |
| critic | C1 done: brief bills total unsourced; specials tile contradicts itself; IMEs conflated | C2 after the draft checker lands, and after the re-digest | | Re-digest won't re-extract or re-score; coverage tile mixes three policies | 00:56 |
| reviewer | | | | | |

## Stubs and shortcuts

New ones only, one line each when written: what, why, file. The hackathon's are in docs/progress.md and docs/tracks/*.md; the README lists both.

- B3: a sync or digest that fails before its run row is held in server memory, so a restart forgets it (backend/app/services/jobs.py)
- B1: the draft checker reads amounts only with $, USD or "dollars", and dates only with a month name or numeric form (backend/app/services/text_mentions.py)
- P9: headline_fact_ids is written beside BriefContent's fields until backend adds it to the contract (backend/app/digest/merge.py)
- P6: a failed model call is not retried until `cli digest --retry-failed`; the run's error says how many were skipped (backend/app/digest/llm.py)
- P13: `cli reextract --dry-run` prices a selection from average recorded costs, an upper bound; cached answers cost less (backend/app/digest/reextract.py)
