# Status

Each role edits only its own row. Keep cells under 15 words. Update with /status. The hackathon's own status is history in docs/progress.md.

| Role | Now | Next | Blocked on | Needs decision | Updated |
|---|---|---|---|---|---|
| lead | Verified U4 and U7 in the browser (lock, remove sentence, brief Differs mark); restarted the API for B5 and B6 | Critic pass 2 once B7 to B10 land | Manager: model settings in the root .env | Approve estimate (a) and (b), about $0.39 | 01:17 |
| pipeline | P7 minor items (split mapping.py, config, dead code, log, JPEG) | P13 prompt and payloads after backend B10 (D21 names) | backend: B10 contract; Manager: .env lacks EXTRACT_MODEL, MERGE_MODEL, four prices | P10: (a) re-digest 4-6 calls ~$0.20; (b) 9 records, 0 pages, ~$0.19 incl. brief | 01:15 |
| backend | B10 contract fc54ed1 (D21) landed: pipeline unblocked. Now B8 | B9, B10 tile | ui-builder: KIND_LABELS needs economic_damages, recovery_cap (typecheck red); lead: restart :8000 | real app.db CHECK on facts.kind rejects new kinds: rebuild table or reset? | 01:18 |
| ui-builder | C-U client half done: 23117ae da9dbfa e113186; labels a04530e; feed 597aa55 | U8 no-bills after B9; U9 after B10; drawer date after B8; Calls types after C-B | backend: C-B types and routes; B8; B9; B10 | lead: CallTargetOut.last_contact_days has no source ref (rule 3) | 01:24 |
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
- P4 known issue: pages read before a provider was known never get that provider. Fix (1): store provider_name_as_written on facts (new column, needs reset or a migration), re-resolve in code after mapping, no model call. Fix (2): re-read pages when the provider list changes, one call per page (backend/app/digest/extract.py)
- C-U: stand-in Calls types mirror docs/calls-contract.md until C-B adds them to types.ts (frontend/src/api/calls.ts)
