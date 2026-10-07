# Status

Each role edits only its own row. Keep cells under 15 words. Update with /status. The hackathon's own status is history in docs/progress.md.

| Role | Now | Next | Blocked on | Needs decision | Updated |
|---|---|---|---|---|---|
| lead | Pipeline finished P7, P13, C-P; critic Pass 2 running; D24 schema upgrade queued with backend | Run upgrade_schema on the real database after backend tests it on a copy | Manager: .env model settings; approve (a), (b) and a re-sync | (a) about $0.20, (b) about $0.19, re-sync free; retry-failed button | 01:58 |
| pipeline | C-P done 9bd8566 113fdef. Backend: extract_call_notes(session, transcript, *, matter_id, call_date, counterpart, retry_failed) -> CallNotes(notes, dropped). CallNoteDraft: kind, text, quote, quote_start, quote_end, amounts_cents, dates [{on, precision}]. Raises ModelsNotConfigured (no_model), CallNotesFailed (failed) | Idle; report to lead | Manager: .env lacks models and prices; (a), (b) wait on D24 upgrade_schema | P10: (a) ~$0.20; (b) ~$0.19 | 01:47 |
| backend | C-B started. Pipeline: agreed, extract_call_notes() as in your row; backend stores drafts as call_note facts on a call source | C-B routes, tests | ui-builder: ProviderRow.tsx:37 null billed_cents (typecheck red); pipeline: received_at in DOCUMENT_FIELDS | | 01:39 |
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
- C-P: a date said on a call without a year is placed at the nearest such day to the call, within six months, else left out (backend/app/digest/call_notes.py)
- P4 known issue: pages read before a provider was known never get that provider. Fix (1): store provider_name_as_written on facts (new column, needs reset or a migration), re-resolve in code after mapping, no model call. Fix (2): re-read pages when the provider list changes, one call per page (backend/app/digest/extract.py)
- C-U: stand-in Calls types mirror docs/calls-contract.md until C-B adds them to types.ts (frontend/src/api/calls.ts)
