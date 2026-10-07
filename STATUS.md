# Status

Each role edits only its own row. Keep cells under 15 words. Update with /status. The hackathon's own status is history in docs/progress.md.

| Role | Now | Next | Blocked on | Needs decision | Updated |
|---|---|---|---|---|---|
| lead | Verified U1, B1 (on the real matter), U8 drawer and preview; restarted Vite and the API | Critic pass 2 after U4 and B4; reviewer near the freeze | Manager: model settings in the root .env | Approve the re-digest and re-extraction estimate when pipeline reports it | 02:50 |
| pipeline | P9 ed773de: brief content_json.headline_fact_ids, list[int], real ids only, may be empty (backend B4). P10 estimated. Now P11 | P12 ledger titles | Manager: .env lacks EXTRACT_MODEL, MERGE_MODEL, four prices | P10: plain re-digest 4-6 calls, ~$0.20; targeted (b) +2 calls ~$0.05, needs prompt fix first | 01:03 |
| backend | B4 brief check. Note: 049da3d changed tile behaviour (one-ended value, occurrence limits, specials basis); B5 repairs | B5, B6, B7, B8, B9 | | | 01:05 |
| ui-builder | U8 done: 6653bb3 d0743a6 ce3dbc8; no-bills text waits on B9 | U7 after B4; U8 rest after B8, B9 | backend: B4 headline facts; B8 document-date field; B9 nullable billed_cents | | 01:00 |
| researcher | Done: briefs/draft-checker.md (backend B1, ui-builder U4); briefs/calls.md (C-B, C-P, C-U) | Idle | lead: commit both briefs; researcher has no shell | Calls: let Manager type a test number, stored locally? | 01:05 |
| critic | C1 done: brief bills total unsourced; specials tile contradicts itself; IMEs conflated | C2 after the draft checker lands, and after the re-digest | | Re-digest won't re-extract or re-score; coverage tile mixes three policies | 00:56 |
| reviewer | | | | | |

## Stubs and shortcuts

New ones only, one line each when written: what, why, file. The hackathon's are in docs/progress.md and docs/tracks/*.md; the README lists both.

- B3: a sync or digest that fails before its run row is held in server memory, so a restart forgets it (backend/app/services/jobs.py)
- B1: the draft checker reads amounts only with $, USD or "dollars", and dates only with a month name or numeric form (backend/app/services/text_mentions.py)
- P9: headline_fact_ids is written beside BriefContent's fields until backend adds it to the contract (backend/app/digest/merge.py)
- P6: a failed model call is not retried until `cli digest --retry-failed`; the run's error says how many were skipped (backend/app/digest/llm.py)
